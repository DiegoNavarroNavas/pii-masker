#!/usr/bin/env python3
"""
Runtime worker for heavy redaction formats.

Runs under the project venv Python when invoked by native_host/host.py.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import Any


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise RuntimeError("Empty worker stdout")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise RuntimeError("No JSON payload found in worker stdout")


def preview_first_lines(text: str, max_lines: int = 10) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    return "\n".join(lines[:max_lines])


def run_masker_text(
    repo_root: Path,
    text: str,
    language: str,
    key_file: str,
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    local_encoder_model: str | None,
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

    proc = subprocess.run(
        [sys.executable, "pii_masker.py", "--json-mode"],
        cwd=str(repo_root),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Masker command failed ({proc.returncode}): {proc.stderr.strip()}")

    response = parse_json_from_stdout(proc.stdout)
    if not response.get("ok"):
        error = response.get("error", {})
        raise RuntimeError(f"Masker error {error.get('code')}: {error.get('message')}")
    return response["masked_text"], response.get("mapping", {})


def redact_pdf(
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
    try:
        from pypdf import PdfReader  # type: ignore
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except ImportError as e:
        raise ModuleNotFoundError(f"Missing PDF dependency: {e}") from e

    reader = PdfReader(BytesIO(content_bytes))
    page_texts: list[str] = []
    for page in reader.pages:
        page_texts.append(page.extract_text() or "")
    source_text = "\f".join(page_texts)

    masked_text, mapping = run_masker_text(
        repo_root,
        source_text,
        language,
        key_file,
        engine,
        model,
        spacy_model,
        transformer_model,
        local_encoder_model,
    )

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    margin = 40
    line_height = 14

    for page_text in masked_text.split("\f"):
        y = height - margin
        for raw_line in page_text.splitlines():
            line = raw_line
            while len(line) > 100:
                pdf.drawString(margin, y, line[:100])
                y -= line_height
                line = line[100:]
                if y <= margin:
                    pdf.showPage()
                    y = height - margin
            pdf.drawString(margin, y, line)
            y -= line_height
            if y <= margin:
                pdf.showPage()
                y = height - margin
        pdf.showPage()

    pdf.save()
    return output.getvalue(), mapping, masked_text


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        payload = json.loads(sys.stdin.read())
        mode = payload.get("mode")
        if mode != "pdf":
            raise ValueError("Unsupported mode")
        content_bytes = base64.b64decode(payload["contentBase64"], validate=True)
        redacted, mapping, masked_text = redact_pdf(
            repo_root=repo_root,
            content_bytes=content_bytes,
            language=payload.get("language", "en"),
            key_file=payload["keyFile"],
            engine=payload.get("engine", "spacy"),
            model=payload.get("model"),
            spacy_model=payload.get("spacy_model"),
            transformer_model=payload.get("transformer_model"),
            local_encoder_model=payload.get("local_encoder_model"),
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "contentBase64": base64.b64encode(redacted).decode("ascii"),
                    "mapping": mapping,
                    "previewFirst10Lines": preview_first_lines(masked_text, 10),
                }
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": {"code": "WORKER_FAILED", "message": str(e)}}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
