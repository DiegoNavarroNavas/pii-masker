#!/usr/bin/env python3
"""
Chrome Native Messaging host for local file redaction.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

MAX_REQUEST_BYTES = 15 * 1024 * 1024
HOST_VERSION = "0.2.0"
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}
SUPPORTED_TEXT_MIME_PREFIXES = ("text/",)
SUPPORTED_MIME_TYPES = {
    "application/json",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
}

def runtime_host_dir() -> Path:
    """Directory where the native host runtime resides."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_logger() -> logging.Logger:
    """Configure file logger for host diagnostics (no PII content)."""
    log_path = os.environ.get("PII_MASKER_HOST_LOG")
    if not log_path:
        log_path = str(runtime_host_dir() / "host.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pii_masker_native_host")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    logger.info("Native host logger initialized path=%s", log_path)
    return logger


LOGGER = configure_logger()


def run_command_with_live_stderr(
    *,
    command: list[str],
    cwd: Path,
    stdin_text: str,
    timeout_seconds: int,
    stderr_log_prefix: str,
) -> tuple[int, str, str]:
    """
    Run command while streaming stderr into host logger in near real time.

    This keeps long-running engine/model initialization visible in host.log,
    instead of logging everything only after the child process exits.
    """
    env = os.environ.copy()
    # Force unbuffered child Python output so progress appears incrementally.
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def read_stdout() -> None:
        assert proc.stdout is not None
        for chunk in iter(lambda: proc.stdout.read(4096), ""):
            stdout_chunks.append(chunk)

    def read_stderr() -> None:
        assert proc.stderr is not None
        pending = ""
        for chunk in iter(lambda: proc.stderr.read(4096), ""):
            stderr_chunks.append(chunk)
            pending += chunk
            parts = re.split(r"[\r\n]+", pending)
            pending = parts.pop() if parts else ""
            for part in parts:
                message = part.strip()
                if message:
                    LOGGER.info("%s%s", stderr_log_prefix, message)
        tail = pending.strip()
        if tail:
            LOGGER.info("%s%s", stderr_log_prefix, tail)

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    assert proc.stdin is not None
    proc.stdin.write(stdin_text)
    proc.stdin.close()

    try:
        return_code = proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

    return return_code, "".join(stdout_chunks), "".join(stderr_chunks)


def read_native_message() -> dict[str, Any] | None:
    """Read one Native Messaging message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None
    message_length = struct.unpack("<I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


def send_native_message(payload: dict[str, Any]) -> None:
    """Write one Native Messaging message to stdout."""
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def is_disconnected_io_error(error: BaseException) -> bool:
    """True when stdio pipe is no longer writable/readable."""
    if isinstance(error, BrokenPipeError):
        return True
    if isinstance(error, OSError):
        # Windows can surface disconnected stdio as Errno 22 (Invalid argument).
        return error.errno in {22, 32}
    return False


def error_response(job_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "error",
        "jobId": job_id,
        "hostVersion": HOST_VERSION,
        "error": {"code": code, "message": message},
    }


def bool_value(data: dict[str, Any], key: str, default: bool = False) -> bool:
    value = data.get(key, default)
    return value if isinstance(value, bool) else default


def parse_semver(value: str) -> tuple[int, int, int] | None:
    """Parse `major.minor.patch` values used by the extension/host handshake."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    if major < 0 or minor < 0 or patch < 0:
        return None
    return major, minor, patch


def host_meets_minimum(min_host_version: str) -> bool:
    min_parsed = parse_semver(min_host_version)
    host_parsed = parse_semver(HOST_VERSION)
    if not min_parsed or not host_parsed:
        return False
    return host_parsed >= min_parsed


def is_text_file(file_name: str, mime_type: str) -> bool:
    extension = Path(file_name).suffix.lower()
    if extension in SUPPORTED_TEXT_EXTENSIONS:
        return True
    return any(mime_type.startswith(prefix) for prefix in SUPPORTED_TEXT_MIME_PREFIXES)


def is_pdf(file_name: str, mime_type: str) -> bool:
    extension = Path(file_name).suffix.lower()
    return extension == ".pdf" or mime_type == "application/pdf"


def preview_first_lines(text: str, max_lines: int = 10) -> str:
    """Return first N lines for debug logging."""
    lines = text.splitlines()
    if not lines:
        return ""
    return "\n".join(lines[:max_lines])


def parse_request(request: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    job_id = request.get("jobId") or str(uuid4())
    required = ("action", "fileName", "mimeType", "contentBase64", "keyFile")
    for field in required:
        if field not in request:
            return None, error_response(job_id, "INVALID_REQUEST", f"Missing field: {field}")
    if request.get("action") != "redact_upload":
        return None, error_response(job_id, "INVALID_REQUEST", "Unsupported action")

    file_name = request["fileName"]
    mime_type = request["mimeType"]
    if not isinstance(file_name, str) or not isinstance(mime_type, str):
        return None, error_response(
            job_id,
            "INVALID_REQUEST",
            "fileName and mimeType must be strings",
        )

    try:
        content_bytes = base64.b64decode(request["contentBase64"], validate=True)
    except Exception:
        return None, error_response(job_id, "INVALID_BASE64", "contentBase64 is invalid")

    if len(content_bytes) > MAX_REQUEST_BYTES:
        return None, error_response(job_id, "REQUEST_TOO_LARGE", "File exceeds 15MB limit")

    parsed = {
        "version": request.get("version", 1),
        "jobId": job_id,
        "fileName": file_name,
        "mimeType": mime_type,
        "contentBytes": content_bytes,
        "language": request.get("language", "en"),
        "engine": request.get("engine", "spacy"),
        "model": request.get("model"),
        "spacyModel": request.get("spacyModel"),
        "transformersModel": request.get("transformersModel"),
        "localEncoderModel": request.get("localEncoderModel"),
        "keyFile": request["keyFile"],
        "minHostVersion": request.get("minHostVersion"),
        "includeMapping": bool_value(request, "includeMapping", False),
    }
    LOGGER.info(
        "request_parsed jobId=%s fileName=%s mimeType=%s sizeBytes=%s language=%s engine=%s model=%s spacyModel=%s transformersModel=%s localEncoderModel=%s includeMapping=%s",
        parsed["jobId"],
        parsed["fileName"],
        parsed["mimeType"],
        len(parsed["contentBytes"]),
        parsed["language"],
        parsed["engine"],
        parsed["model"],
        parsed["spacyModel"],
        parsed["transformersModel"],
        parsed["localEncoderModel"],
        parsed["includeMapping"],
    )
    return parsed, None


def default_vault_dir() -> Path:
    env_path = os.environ.get("PII_MASKER_VAULT_DIR")
    if isinstance(env_path, str) and env_path.strip():
        return Path(env_path).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if isinstance(local_app_data, str) and local_app_data.strip():
            return Path(local_app_data) / "PIIMasker" / "vaults"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PIIMasker" / "vaults"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if isinstance(xdg_data_home, str) and xdg_data_home.strip():
        return Path(xdg_data_home) / "pii-masker" / "vaults"
    return Path.home() / ".local" / "share" / "pii-masker" / "vaults"


def save_vault_record(
    *,
    job_id: str,
    original_file_name: str,
    redacted_file_name: str,
    mime_type: str,
    language: str,
    engine: str,
    key_file: str,
    mapping: dict[str, Any],
) -> Path:
    vault_dir = default_vault_dir()
    vault_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "id": str(uuid4()),
        "jobId": job_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "originalFileName": original_file_name,
        "redactedFileName": redacted_file_name,
        "mimeType": mime_type,
        "language": language,
        "engine": engine,
        "keyFile": key_file,
        "mapping": mapping,
    }
    output_file = vault_dir / f"{timestamp}_{job_id}.vault.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_file


def process_get_vault_dir_request(request: dict[str, Any]) -> dict[str, Any]:
    job_id = request.get("jobId") or str(uuid4())
    min_host_version = request.get("minHostVersion")
    if isinstance(min_host_version, str) and min_host_version.strip():
        if not host_meets_minimum(min_host_version):
            return error_response(
                job_id,
                "HOST_VERSION_UNSUPPORTED",
                (
                    f"Native host {HOST_VERSION} is older than required "
                    f"minimum {min_host_version}. Please update the companion app."
                ),
            )
    vault_dir = default_vault_dir()
    exists = vault_dir.exists()
    return {
        "ok": True,
        "status": "ok",
        "jobId": job_id,
        "hostVersion": HOST_VERSION,
        "vaultDirectory": str(vault_dir),
        "exists": exists,
    }


def masker_command(repo_root: Path) -> list[str]:
    env_command = os.environ.get("PII_MASKER_CMD")
    if env_command:
        # Space-separated command override, e.g.:
        # PII_MASKER_CMD="uv run python pii_masker.py --json-mode"
        return env_command.split(" ")
    venv_python_windows = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_unix = repo_root / ".venv" / "bin" / "python"
    if venv_python_windows.exists():
        return [str(venv_python_windows), "pii_masker.py", "--json-mode"]
    if venv_python_unix.exists():
        return [str(venv_python_unix), "pii_masker.py", "--json-mode"]
    if os.name == "nt":
        uv_exe = shutil.which("uv")
        if uv_exe:
            return [uv_exe, "run", "python", "pii_masker.py", "--json-mode"]
    return [sys.executable, "pii_masker.py", "--json-mode"]


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    """
    Parse JSON response even when tools print extra logs before JSON.

    Some environments emit model-install output before the actual JSON payload.
    """
    text = stdout.strip()
    if not text:
        raise RuntimeError("Masker returned empty stdout")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate or not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise RuntimeError("Masker returned invalid JSON")


def runtime_worker_command(repo_root: Path) -> list[str]:
    """Command for the venv worker handling runtime-heavy formats."""
    worker_script = repo_root / "native_host" / "runtime_worker.py"
    venv_python_windows = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_unix = repo_root / ".venv" / "bin" / "python"
    if venv_python_windows.exists():
        return [str(venv_python_windows), str(worker_script)]
    if venv_python_unix.exists():
        return [str(venv_python_unix), str(worker_script)]
    return [sys.executable, str(worker_script)]


def run_masker_text(
    repo_root: Path,
    text: str,
    language: str,
    key_file: str,
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    local_encoder_model: str | None = None,
    timeout_seconds: int = 120,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "action": "anonymize",
        "text": text,
        "language": language,
        "engine": engine,
        "key_file": key_file,
    }
    if model:
        payload["model"] = model
    if spacy_model:
        payload["spacy_model"] = spacy_model
    if transformer_model:
        payload["transformer_model"] = transformer_model
    if local_encoder_model:
        payload["local_encoder_model"] = local_encoder_model
    command = masker_command(repo_root)
    LOGGER.info(
        "run_masker_start command=%s language=%s engine=%s keyFile=%s",
        command,
        language,
        engine,
        key_file,
    )
    try:
        return_code, stdout_text, stderr_text = run_command_with_live_stderr(
            command=command,
            cwd=repo_root,
            stdin_text=json.dumps(payload),
            timeout_seconds=timeout_seconds,
            stderr_log_prefix="masker_stderr ",
        )
    except subprocess.TimeoutExpired:
        LOGGER.error("run_masker_timeout timeoutSeconds=%s", timeout_seconds)
        raise TimeoutError("Masker command timed out")

    parsed_response: dict[str, Any] | None = None
    if stdout_text.strip():
        try:
            parsed_response = parse_json_from_stdout(stdout_text)
        except Exception:
            parsed_response = None

    if return_code != 0:
        if parsed_response and not parsed_response.get("ok"):
            error = parsed_response.get("error", {})
            code = error.get("code", "UNKNOWN")
            message = error.get("message", "Unknown error")
            LOGGER.error(
                "run_masker_response_error returnCode=%s code=%s message=%s",
                return_code,
                code,
                message,
            )
            if code in {"DEPENDENCY_OR_ENGINE_ERROR", "UNSUPPORTED_ENGINE"}:
                raise ModuleNotFoundError(f"{code}: {message}")
            raise RuntimeError(f"Masker error {code}: {message}")

        stderr = stderr_text.strip()
        LOGGER.error(
            "run_masker_failed returnCode=%s stderr=%s",
            return_code,
            stderr[:800],
        )
        raise RuntimeError(f"Masker command failed ({return_code}): {stderr}")

    if not parsed_response:
        LOGGER.error("run_masker_invalid_json stdoutPrefix=%s", stdout_text[:800])
        raise RuntimeError("Masker returned invalid JSON")

    if not parsed_response.get("ok"):
        error = parsed_response.get("error", {})
        code = error.get("code", "UNKNOWN")
        message = error.get("message", "Unknown error")
        LOGGER.error("run_masker_response_error code=%s message=%s", code, message)
        if code in {"DEPENDENCY_OR_ENGINE_ERROR", "UNSUPPORTED_ENGINE"}:
            raise ModuleNotFoundError(f"{code}: {message}")
        raise RuntimeError(f"Masker error {code}: {message}")

    LOGGER.info("run_masker_success mappingCount=%s", len(parsed_response.get("mapping", {})))
    return parsed_response["masked_text"], parsed_response.get("mapping", {})


def redact_text_file(
    repo_root: Path,
    content_bytes: bytes,
    file_name: str,
    language: str,
    key_file: str,
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    local_encoder_model: str | None,
) -> tuple[bytes, dict[str, Any]]:
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Text decoding failed: {e}") from e
    masked_text, mapping = run_masker_text(
        repo_root,
        text,
        language,
        key_file,
        engine,
        model,
        spacy_model,
        transformer_model,
        local_encoder_model,
    )
    LOGGER.info(
        "redacted_text_preview_first_10_lines\n%s",
        preview_first_lines(masked_text, 10),
    )
    return masked_text.encode("utf-8"), mapping


def redact_pdf_file(
    repo_root: Path,
    content_bytes: bytes,
    language: str,
    key_file: str,
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    local_encoder_model: str | None,
) -> tuple[bytes, dict[str, Any]]:
    worker_payload = {
        "mode": "pdf",
        "contentBase64": base64.b64encode(content_bytes).decode("ascii"),
        "language": language,
        "keyFile": key_file,
        "engine": engine,
        "model": model,
        "spacy_model": spacy_model,
        "transformer_model": transformer_model,
        "local_encoder_model": local_encoder_model,
    }
    command = runtime_worker_command(repo_root)
    LOGGER.info("run_pdf_worker_start command=%s", command)
    try:
        return_code, stdout_text, stderr_text = run_command_with_live_stderr(
            command=command,
            cwd=repo_root,
            stdin_text=json.dumps(worker_payload),
            timeout_seconds=180,
            stderr_log_prefix="pdf_worker_stderr ",
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("PDF worker failed (timeout): process exceeded 180s")
    if return_code != 0:
        parsed_response: dict[str, Any] | None = None
        if stdout_text.strip():
            try:
                parsed_response = parse_json_from_stdout(stdout_text)
            except Exception:
                parsed_response = None

        if parsed_response and not parsed_response.get("ok"):
            error = parsed_response.get("error", {})
            code = error.get("code", "UNKNOWN")
            message = error.get("message", "Unknown error")
            raise RuntimeError(f"PDF worker failed ({return_code}) {code}: {message}")

        stderr = stderr_text.strip()
        if stderr:
            raise RuntimeError(f"PDF worker failed ({return_code}): {stderr}")

        stdout = stdout_text.strip()
        if stdout:
            raise RuntimeError(f"PDF worker failed ({return_code}): {stdout[:800]}")

        raise RuntimeError(f"PDF worker failed ({return_code}): no stderr/stdout output")

    try:
        response = parse_json_from_stdout(stdout_text)
    except Exception as e:
        LOGGER.error("run_pdf_worker_invalid_json stdoutPrefix=%s", stdout_text[:800])
        raise RuntimeError(f"PDF worker returned invalid JSON: {e}") from e

    if not response.get("ok"):
        error = response.get("error", {})
        code = error.get("code", "UNKNOWN")
        message = error.get("message", "Unknown error")
        raise ModuleNotFoundError(f"{code}: {message}")

    redacted_bytes = base64.b64decode(response["contentBase64"])
    mapping = response.get("mapping", {})
    preview_lines = response.get("previewFirst10Lines")
    if isinstance(preview_lines, str) and preview_lines:
        LOGGER.info("redacted_pdf_text_preview_first_10_lines\n%s", preview_lines)
    return redacted_bytes, mapping


def process_request(repo_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if request.get("action") == "get_vault_dir":
        return process_get_vault_dir_request(request)

    parsed, error = parse_request(request)
    if error:
        LOGGER.error(
            "request_invalid jobId=%s code=%s message=%s",
            error.get("jobId"),
            error.get("error", {}).get("code"),
            error.get("error", {}).get("message"),
        )
        return error
    assert parsed is not None

    file_name = parsed["fileName"]
    mime_type = parsed["mimeType"]
    content_bytes = parsed["contentBytes"]
    language = parsed["language"]
    key_file = parsed["keyFile"]
    engine = parsed["engine"]
    model = parsed["model"]
    spacy_model = parsed["spacyModel"]
    transformer_model = parsed["transformersModel"]
    local_encoder_model = parsed["localEncoderModel"]
    job_id = parsed["jobId"]
    include_mapping = parsed["includeMapping"]
    min_host_version = parsed["minHostVersion"]

    if isinstance(min_host_version, str) and min_host_version.strip():
        if not host_meets_minimum(min_host_version):
            LOGGER.warning(
                "host_version_unsupported jobId=%s hostVersion=%s minHostVersion=%s",
                job_id,
                HOST_VERSION,
                min_host_version,
            )
            return error_response(
                job_id,
                "HOST_VERSION_UNSUPPORTED",
                (
                    f"Native host {HOST_VERSION} is older than required "
                    f"minimum {min_host_version}. Please update the companion app."
                ),
            )

    try:
        if is_pdf(file_name, mime_type):
            redacted_bytes, mapping = redact_pdf_file(
                repo_root,
                content_bytes,
                language,
                key_file,
                engine,
                model,
                spacy_model,
                transformer_model,
                local_encoder_model,
            )
            output_name = f"{Path(file_name).stem}.redacted.pdf"
            output_mime = "application/pdf"
        elif is_text_file(file_name, mime_type):
            redacted_bytes, mapping = redact_text_file(
                repo_root,
                content_bytes,
                file_name,
                language,
                key_file,
                engine,
                model,
                spacy_model,
                transformer_model,
                local_encoder_model,
            )
            output_name = f"{Path(file_name).stem}.redacted{Path(file_name).suffix}"
            output_mime = mime_type if mime_type in SUPPORTED_MIME_TYPES else "text/plain"
        else:
            LOGGER.warning("unsupported_file_type jobId=%s fileName=%s mimeType=%s", job_id, file_name, mime_type)
            return error_response(
                job_id,
                "UNSUPPORTED_FILE_TYPE",
                "Only PDF and text formats (.txt, .md, .csv, .json) are supported in v1.",
            )
    except ModuleNotFoundError as e:
        LOGGER.error("dependency_missing jobId=%s error=%s", job_id, e)
        return error_response(job_id, "DEPENDENCY_MISSING", str(e))
    except TimeoutError as e:
        LOGGER.error("masker_timeout jobId=%s error=%s", job_id, e)
        return error_response(job_id, "MASKER_TIMEOUT", str(e))
    except ValueError as e:
        if "Text decoding failed" in str(e):
            LOGGER.error("text_encoding_unsupported jobId=%s error=%s", job_id, e)
            return error_response(job_id, "UNSUPPORTED_TEXT_ENCODING", str(e))
        LOGGER.error("request_value_error jobId=%s error=%s", job_id, e)
        return error_response(job_id, "INVALID_REQUEST", str(e))
    except RuntimeError as e:
        LOGGER.error("masker_command_failed jobId=%s error=%s", job_id, e)
        return error_response(job_id, "MASKER_COMMAND_FAILED", str(e))
    except Exception as e:
        LOGGER.exception("internal_error jobId=%s", job_id)
        return error_response(job_id, "INTERNAL_ERROR", str(e))

    response: dict[str, Any] = {
        "ok": True,
        "status": "ok",
        "jobId": job_id,
        "hostVersion": HOST_VERSION,
        "fileName": output_name,
        "mimeType": output_mime,
        "contentBase64": base64.b64encode(redacted_bytes).decode("ascii"),
    }
    if include_mapping:
        response["mapping"] = mapping
    try:
        output_file = save_vault_record(
            job_id=job_id,
            original_file_name=file_name,
            redacted_file_name=output_name,
            mime_type=output_mime,
            language=language,
            engine=engine,
            key_file=key_file,
            mapping=mapping,
        )
        response["vaultFile"] = str(output_file)
    except Exception as save_error:
        LOGGER.warning("vault_save_failed jobId=%s error=%s", job_id, save_error)
    LOGGER.info(
        "request_success jobId=%s outputFile=%s outputMime=%s outputBytes=%s mappingCount=%s",
        job_id,
        output_name,
        output_mime,
        len(redacted_bytes),
        len(mapping),
    )
    return response


def main() -> int:
    repo_root = runtime_host_dir().parent
    LOGGER.info("native_host_start repoRoot=%s", repo_root)
    while True:
        try:
            request = read_native_message()
            if request is None:
                LOGGER.info("native_host_stdin_closed")
                return 0
            response = process_request(repo_root, request)
            send_native_message(response)
        except Exception as e:
            if is_disconnected_io_error(e):
                LOGGER.info("native_host_io_disconnected; exiting loop")
                return 0
            LOGGER.exception("native_host_loop_error")
            try:
                send_native_message(error_response(str(uuid4()), "INTERNAL_ERROR", str(e)))
            except Exception as send_error:
                if is_disconnected_io_error(send_error):
                    LOGGER.info("native_host_error_reply_failed_due_to_disconnected_io; exiting")
                    return 0
                LOGGER.exception("native_host_error_reply_send_failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
