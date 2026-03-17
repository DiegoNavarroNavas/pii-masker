#!/usr/bin/env python3
"""
Desktop restore UI for exported redaction vaults.

Usage:
    python scripts/desktop/unredact_manager.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import StringVar, Tk, filedialog, messagebox, ttk


TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json"}
PDF_SUFFIX = ".pdf"


def repo_root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def masker_command(repo_root: Path) -> list[str]:
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


def parse_json_from_stdout(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        raise RuntimeError("Masker returned empty stdout")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate or not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    raise RuntimeError("Masker returned invalid JSON")


def is_safe_member(path_name: str) -> bool:
    path = Path(path_name)
    if path.is_absolute():
        return False
    for part in path.parts:
        if part == "..":
            return False
    return True


def extract_zip_safely(zip_path: Path, output_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.namelist():
            if not is_safe_member(member):
                raise ValueError(f"Unsafe ZIP entry blocked: {member}")
        archive.extractall(output_dir)


def require_pdf_dependencies() -> None:
    missing: list[str] = []
    try:
        import pypdf  # type: ignore  # noqa: F401
    except ImportError:
        missing.append("pypdf")
    try:
        import reportlab  # type: ignore  # noqa: F401
    except ImportError:
        missing.append("reportlab")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required dependency/dependencies: {joined}. Install project dependencies before launching."
        )


def create_vault_icon() -> tk.PhotoImage:
    image = tk.PhotoImage(width=32, height=32)
    image.put("#1A1F2B", to=(0, 0, 32, 32))
    image.put("#2A3142", to=(2, 2, 30, 30))
    image.put("#141925", to=(3, 3, 29, 29))

    # Light blue up arrow (unpack/restore)
    arrow = "#7FD6FF"
    shadow = "#2F8AB4"
    image.put(arrow, to=(14, 12, 18, 24))
    image.put(arrow, to=(10, 10, 22, 14))
    image.put(arrow, to=(11, 9, 21, 12))
    image.put(arrow, to=(12, 7, 20, 10))
    image.put(arrow, to=(13, 5, 19, 8))
    image.put(shadow, to=(18, 12, 19, 24))
    image.put(shadow, to=(22, 10, 23, 14))
    return image


def normalize_mapping(raw_mapping: object) -> dict[str, list[str]]:
    if not isinstance(raw_mapping, dict):
        raise ValueError("Vault mapping must be an object")
    normalized: dict[str, list[str]] = {}
    for placeholder, value in raw_mapping.items():
        if not isinstance(placeholder, str):
            continue
        if isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value):
            normalized[placeholder] = [value[0], value[1]]
        elif isinstance(value, dict):
            entity_type = value.get("entity_type")
            encrypted = value.get("encrypted")
            if isinstance(entity_type, str) and isinstance(encrypted, str):
                normalized[placeholder] = [entity_type, encrypted]
    return normalized


@dataclass
class VaultRecord:
    path: Path
    original_file_name: str
    redacted_file_name: str
    key_file: str
    mapping: dict[str, list[str]]


@dataclass
class RestoreResult:
    restored: int
    skipped: int
    failed: int
    details: list[str]


class UnredactManagerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("PII Masker Unredact Manager")
        self.icon_image = create_vault_icon()
        self.root.iconphoto(True, self.icon_image)
        self.status_var = StringVar(value="Select vault ZIP, keys ZIP, and redacted files or folder.")

        self.vault_zip_var = StringVar()
        self.keys_zip_var = StringVar()
        self.redacted_input_var = StringVar(value="No redacted input selected")
        self.selected_redacted_files: list[Path] = []
        self.selected_redacted_dir: Path | None = None
        self.output_dir_var = StringVar(value=str((repo_root_dir() / "results" / "restored").resolve()))

        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

        self._add_file_picker_row(frame, 0, "Vault ZIP", self.vault_zip_var, self.pick_vault_zip)
        self._add_file_picker_row(frame, 1, "Keys ZIP", self.keys_zip_var, self.pick_keys_zip)
        self._add_redacted_picker_row(frame, 2, "Redacted Docs", self.redacted_input_var)
        self._add_file_picker_row(frame, 3, "Output Folder", self.output_dir_var, self.pick_output_dir, pick_dir=True)

        button_row = ttk.Frame(frame)
        button_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        button_row.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(button_row, text="Preview Matches", command=self.preview_matches).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(button_row, text="Run Unredact", command=self.run_unredact).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(button_row, text="Clear", command=self.clear_fields).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        preview_frame = ttk.Frame(frame)
        preview_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        preview_columns = ("expected", "source", "status")
        self.preview_tree = ttk.Treeview(preview_frame, columns=preview_columns, show="headings", height=8)
        self.preview_tree.heading("expected", text="Expected redacted filename")
        self.preview_tree.heading("source", text="Matched source")
        self.preview_tree.heading("status", text="Status")
        self.preview_tree.column("expected", width=280, anchor="w")
        self.preview_tree.column("source", width=420, anchor="w")
        self.preview_tree.column("status", width=120, anchor="center")
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)
        ttk.Label(frame, textvariable=self.status_var, wraplength=860).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(
            frame,
            text="Supported restore types: .txt, .md, .csv, .json, .pdf. PDF uses text extraction and text re-rendering.",
            wraplength=860,
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))

        details_header = ttk.Frame(frame)
        details_header.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        details_header.columnconfigure(0, weight=1)
        ttk.Label(details_header, text="Run details (copyable)").grid(row=0, column=0, sticky="w")
        ttk.Button(details_header, text="Copy Details", command=self.copy_details).grid(row=0, column=1, sticky="e", padx=(8, 4))
        ttk.Button(details_header, text="Clear Details", command=self.clear_details).grid(row=0, column=2, sticky="e")

        details_frame = ttk.Frame(frame)
        details_frame.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(0, weight=1)
        self.details_text = tk.Text(details_frame, wrap="word", height=10)
        self.details_text.grid(row=0, column=0, sticky="nsew")
        details_scroll = ttk.Scrollbar(details_frame, orient="vertical", command=self.details_text.yview)
        details_scroll.grid(row=0, column=1, sticky="ns")
        self.details_text.configure(yscrollcommand=details_scroll.set)
        self.details_text.insert("1.0", "Run output and errors will appear here.\n")
        self.details_text.configure(state="disabled")

    def _add_file_picker_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: StringVar,
        callback: object,
        pick_dir: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        button_text = "Browse Folder" if pick_dir else "Browse"
        ttk.Button(parent, text=button_text, command=callback).grid(row=row, column=2, sticky="ew", padx=(8, 0), pady=4)

    def _add_redacted_picker_row(self, parent: ttk.Frame, row: int, label: str, variable: StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        controls = ttk.Frame(parent)
        controls.grid(row=row, column=2, sticky="ew", padx=(8, 0), pady=4)
        ttk.Button(controls, text="Pick Files", command=self.pick_redacted_files).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(controls, text="Pick Folder", command=self.pick_redacted_folder).grid(row=0, column=1, sticky="ew")

    def pick_vault_zip(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select exported vault ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if selected:
            self.vault_zip_var.set(selected)
            self.preview_matches()

    def pick_keys_zip(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select exported keys ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if selected:
            self.keys_zip_var.set(selected)

    def pick_redacted_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select one or more redacted files",
            filetypes=[("All files", "*.*")],
        )
        if selected:
            self.selected_redacted_files = [Path(path).expanduser() for path in selected]
            self.selected_redacted_dir = None
            self.redacted_input_var.set(f"{len(self.selected_redacted_files)} file(s) selected")
            self.preview_matches()

    def pick_redacted_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select folder containing redacted files")
        if selected:
            self.selected_redacted_dir = Path(selected).expanduser()
            self.selected_redacted_files = []
            self.redacted_input_var.set(str(self.selected_redacted_dir))
            self.preview_matches()

    def pick_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="Select folder for restored output")
        if selected:
            self.output_dir_var.set(selected)

    def clear_fields(self) -> None:
        self.vault_zip_var.set("")
        self.keys_zip_var.set("")
        self.redacted_input_var.set("No redacted input selected")
        self.selected_redacted_files = []
        self.selected_redacted_dir = None
        for item_id in self.preview_tree.get_children():
            self.preview_tree.delete(item_id)
        self.status_var.set("Cleared. Select vault ZIP, keys ZIP, and redacted files or folder.")
        self.clear_details()

    def set_details(self, text: str) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", text.rstrip() + "\n")
        self.details_text.configure(state="disabled")

    def clear_details(self) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", "Run output and errors will appear here.\n")
        self.details_text.configure(state="disabled")

    def copy_details(self) -> None:
        content = self.details_text.get("1.0", "end").strip()
        if not content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)

    def preview_matches(self) -> None:
        for item_id in self.preview_tree.get_children():
            self.preview_tree.delete(item_id)

        vault_zip_value = self.vault_zip_var.get().strip()
        if not vault_zip_value:
            self.status_var.set("Pick a vault ZIP to preview expected filenames.")
            return
        vault_zip = Path(vault_zip_value).expanduser()
        if not vault_zip.is_file():
            self.status_var.set("Vault ZIP path is invalid. Cannot build preview.")
            return
        if self.selected_redacted_dir is None and not self.selected_redacted_files:
            self.status_var.set("Pick redacted files or folder to preview matches.")
            return

        try:
            expected_names = self.load_expected_redacted_names(vault_zip)
        except Exception as exc:
            self.status_var.set(f"Preview failed: {exc}")
            return
        if not expected_names:
            self.status_var.set("No vault records found in vault ZIP for preview.")
            return

        file_index: dict[str, Path] = {}
        for file_path in self.selected_redacted_files:
            file_index[file_path.name] = file_path

        found_count = 0
        for expected in expected_names:
            matched = self.resolve_source_file(self.selected_redacted_dir, file_index, expected)
            if matched is None:
                self.preview_tree.insert("", "end", values=(expected, "", "Missing"))
            else:
                found_count += 1
                self.preview_tree.insert("", "end", values=(expected, str(matched), "Found"))
        self.status_var.set(f"Preview: found {found_count} of {len(expected_names)} expected redacted files.")

    def load_expected_redacted_names(self, vault_zip: Path) -> list[str]:
        names: list[str] = []
        with tempfile.TemporaryDirectory(prefix="pii-masker-preview-") as temp_dir:
            extracted = Path(temp_dir) / "vaults"
            extracted.mkdir(parents=True, exist_ok=True)
            extract_zip_safely(vault_zip, extracted)
            for vault_path in sorted(extracted.rglob("*.vault.json")):
                try:
                    payload = json.loads(vault_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                redacted_name = payload.get("redactedFileName") if isinstance(payload, dict) else None
                if isinstance(redacted_name, str) and redacted_name.strip():
                    names.append(redacted_name)
        return names

    def run_unredact(self) -> None:
        try:
            result = self._run_unredact_impl()
        except Exception as exc:
            messagebox.showerror("Unredact failed", str(exc))
            self.status_var.set(f"Unredact failed: {exc}")
            self.set_details(str(exc))
            return

        self.status_var.set(
            f"Restored {result.restored} file(s), skipped {result.skipped}, failed {result.failed}."
        )
        full_details = "\n".join(result.details) if result.details else "(no details)"
        self.set_details(full_details)
        details = "\n".join(result.details[:20])
        if len(result.details) > 20:
            details += "\n... additional entries omitted ..."
        messagebox.showinfo(
            "Unredact finished",
            (
                f"Restored: {result.restored}\n"
                f"Skipped: {result.skipped}\n"
                f"Failed: {result.failed}\n\n"
                f"Details:\n{details if details else '(no details)'}"
            ),
        )

    def _run_unredact_impl(self) -> RestoreResult:
        vault_zip = Path(self.vault_zip_var.get().strip()).expanduser()
        keys_zip = Path(self.keys_zip_var.get().strip()).expanduser()
        output_dir = Path(self.output_dir_var.get().strip()).expanduser()

        if not vault_zip.is_file():
            raise ValueError("Vault ZIP path is invalid or missing.")
        if not keys_zip.is_file():
            raise ValueError("Keys ZIP path is invalid or missing.")
        source_dir = self.selected_redacted_dir
        source_files = self.selected_redacted_files
        if source_dir is None and not source_files:
            raise ValueError("Select redacted input files or a redacted input folder.")
        if source_dir is not None and not source_dir.exists():
            raise ValueError("Selected redacted input folder does not exist.")
        if source_dir is not None and not source_dir.is_dir():
            raise ValueError("Selected redacted input folder is not a directory.")
        if source_files:
            missing = [str(path) for path in source_files if not path.exists() or not path.is_file()]
            if missing:
                raise ValueError(f"Some selected redacted files are missing: {missing[0]}")
        output_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="pii-masker-unredact-") as temp_dir:
            temp_root = Path(temp_dir)
            extracted_vaults = temp_root / "vaults"
            extracted_keys = temp_root / "keys"
            extracted_vaults.mkdir(parents=True, exist_ok=True)
            extracted_keys.mkdir(parents=True, exist_ok=True)

            extract_zip_safely(vault_zip, extracted_vaults)
            extract_zip_safely(keys_zip, extracted_keys)

            records = self.load_vault_records(extracted_vaults)
            if not records:
                raise ValueError("No vault records found in vault ZIP.")

            key_files = [p for p in extracted_keys.rglob("*") if p.is_file()]
            if not key_files:
                raise ValueError("No key files found in keys ZIP.")

            return self.restore_records(records, key_files, source_dir, source_files, output_dir)

    def load_vault_records(self, extracted_vaults: Path) -> list[VaultRecord]:
        records: list[VaultRecord] = []
        for vault_path in sorted(extracted_vaults.rglob("*.vault.json")):
            try:
                payload = json.loads(vault_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            mapping = normalize_mapping(payload.get("mapping"))
            redacted_name = payload.get("redactedFileName")
            original_name = payload.get("originalFileName")
            key_file = payload.get("keyFile")
            if not isinstance(redacted_name, str) or not redacted_name.strip():
                continue
            if not isinstance(original_name, str) or not original_name.strip():
                original_name = redacted_name
            if not isinstance(key_file, str):
                key_file = ""
            records.append(
                VaultRecord(
                    path=vault_path,
                    original_file_name=original_name,
                    redacted_file_name=redacted_name,
                    key_file=key_file,
                    mapping=mapping,
                )
            )
        return records

    def restore_records(
        self,
        records: list[VaultRecord],
        key_files: list[Path],
        redacted_dir: Path | None,
        redacted_files: list[Path],
        output_dir: Path,
    ) -> RestoreResult:
        restored = 0
        skipped = 0
        failed = 0
        details: list[str] = []
        chosen_key_cache: dict[str, Path] = {}
        file_index: dict[str, Path] = {}
        for file_path in redacted_files:
            file_index[file_path.name] = file_path

        for record in records:
            source_file = self.resolve_source_file(redacted_dir, file_index, record.redacted_file_name)
            if source_file is None:
                skipped += 1
                details.append(f"SKIP {record.redacted_file_name}: redacted file not found in selected input")
                continue

            if source_file.suffix.lower() not in TEXT_SUFFIXES:
                if source_file.suffix.lower() != PDF_SUFFIX:
                    skipped += 1
                    details.append(f"SKIP {source_file.name}: unsupported file type for restore")
                    continue

            if not record.mapping:
                skipped += 1
                details.append(f"SKIP {source_file.name}: vault mapping is empty")
                continue

            try:
                key_file = self.resolve_key_for_record(record, key_files, chosen_key_cache)
            except Exception as exc:
                failed += 1
                details.append(f"FAIL {source_file.name}: {exc}")
                continue

            try:
                output_path = self.next_available_output(output_dir / record.original_file_name)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if source_file.suffix.lower() == PDF_SUFFIX:
                    restored_pdf = self.restore_pdf_bytes(source_file, record.mapping, key_file)
                    output_path.write_bytes(restored_pdf)
                else:
                    try:
                        masked_text = source_file.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        skipped += 1
                        details.append(f"SKIP {source_file.name}: file is not UTF-8 text")
                        continue
                    restored_text = self.run_deanonymize(masked_text, record.mapping, key_file)
                    output_path.write_text(restored_text, encoding="utf-8")
                restored += 1
                details.append(f"OK {source_file.name} -> {output_path.name}")
            except Exception as exc:
                failed += 1
                details.append(f"FAIL {source_file.name}: {exc}")

        return RestoreResult(restored=restored, skipped=skipped, failed=failed, details=details)

    def resolve_source_file(self, redacted_dir: Path | None, file_index: dict[str, Path], expected_name: str) -> Path | None:
        from_files = file_index.get(expected_name)
        if from_files and from_files.is_file():
            return from_files
        if redacted_dir is not None:
            candidate = redacted_dir / expected_name
            if candidate.is_file():
                return candidate
        return None

    def resolve_key_for_record(
        self,
        record: VaultRecord,
        key_files: list[Path],
        cache: dict[str, Path],
    ) -> Path:
        preferred_name = Path(record.key_file).name if record.key_file else ""

        if preferred_name and preferred_name in cache and cache[preferred_name].exists():
            return cache[preferred_name]

        candidates: list[Path] = []
        if preferred_name:
            candidates.extend([path for path in key_files if path.name == preferred_name])
            candidates.extend([path for path in key_files if path.name.startswith(Path(preferred_name).stem)])
        for key_file in key_files:
            if key_file not in candidates:
                candidates.append(key_file)

        first_placeholder = next(iter(record.mapping))
        probe_mapping = {first_placeholder: record.mapping[first_placeholder]}
        probe_text = first_placeholder

        for key_file in candidates:
            try:
                self.run_deanonymize(probe_text, probe_mapping, key_file)
                if preferred_name:
                    cache[preferred_name] = key_file
                return key_file
            except Exception:
                continue

        raise RuntimeError("No matching key in keys ZIP can decrypt this vault mapping")

    def run_deanonymize(self, text: str, mapping: dict[str, list[str]], key_file: Path) -> str:
        payload = {
            "action": "deanonymize",
            "text": text,
            "mapping": mapping,
            "key_file": str(key_file),
        }
        command = masker_command(repo_root_dir())
        run_env = os.environ.copy()
        run_env["PYTHONIOENCODING"] = "utf-8"
        run_env.setdefault("PYTHONUTF8", "1")
        result = subprocess.run(
            command,
            cwd=str(repo_root_dir()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=json.dumps(payload, ensure_ascii=False),
            env=run_env,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Masker command failed with exit code {result.returncode}: {details}")

        response = parse_json_from_stdout(result.stdout)
        if not response.get("ok"):
            error = response.get("error", {})
            message = error.get("message") or str(error) or "Unknown deanonymize error"
            raise RuntimeError(str(message))
        restored = response.get("text")
        if not isinstance(restored, str):
            raise RuntimeError("Masker response missing restored text")
        return restored

    def restore_pdf_bytes(self, source_file: Path, mapping: dict[str, list[str]], key_file: Path) -> bytes:
        try:
            from pypdf import PdfReader  # type: ignore
            from reportlab.lib.pagesizes import letter  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
        except ImportError as exc:
            raise RuntimeError(f"Missing PDF dependency: {exc}") from exc

        reader = PdfReader(BytesIO(source_file.read_bytes()))
        page_texts: list[str] = []
        for page in reader.pages:
            page_texts.append(page.extract_text() or "")
        masked_text = "\f".join(page_texts)
        restored_text = self.run_deanonymize(masked_text, mapping, key_file)

        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=letter)
        width, height = letter
        margin = 40
        line_height = 14

        for page_text in restored_text.split("\f"):
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
        return output.getvalue()

    def next_available_output(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 2
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


def main() -> int:
    require_pdf_dependencies()
    root = Tk()
    root.geometry("1020x620")
    app = UnredactManagerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
