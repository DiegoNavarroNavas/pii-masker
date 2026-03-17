#!/usr/bin/env python3
"""
Desktop vault manager for exported redaction mappings.

Usage:
    python scripts/desktop/vault_manager.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import BooleanVar, StringVar, Tk, ttk, messagebox, filedialog


def default_vault_dir() -> Path:
    env_path = os.environ.get("PII_MASKER_VAULT_DIR")
    if env_path:
        return Path(env_path).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "PIIMasker" / "vaults"
    if os.name == "posix" and os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "PIIMasker" / "vaults"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "pii-masker" / "vaults"
    return Path.home() / ".local" / "share" / "pii-masker" / "vaults"


def repo_root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def masker_command(repo_root: Path) -> list[str]:
    venv_python_windows = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_unix = repo_root / ".venv" / "bin" / "python"
    if venv_python_windows.exists():
        return [str(venv_python_windows), "pii_masker.py"]
    if venv_python_unix.exists():
        return [str(venv_python_unix), "pii_masker.py"]
    if os.name == "nt":
        uv_exe = shutil.which("uv")
        if uv_exe:
            return [uv_exe, "run", "python", "pii_masker.py"]
    return [sys.executable, "pii_masker.py"]


def create_locked_vault_icon() -> tk.PhotoImage:
    image = tk.PhotoImage(width=32, height=32)
    image.put("#1A1F2B", to=(0, 0, 32, 32))
    image.put("#2A3142", to=(2, 2, 30, 30))
    image.put("#141925", to=(3, 3, 29, 29))

    # Yellow down arrow (pack/export)
    arrow = "#FFD24A"
    shadow = "#B88B18"
    image.put(arrow, to=(14, 8, 18, 20))
    image.put(arrow, to=(10, 18, 22, 22))
    image.put(arrow, to=(11, 20, 21, 23))
    image.put(arrow, to=(12, 22, 20, 25))
    image.put(arrow, to=(13, 24, 19, 27))
    image.put(shadow, to=(18, 8, 19, 20))
    image.put(shadow, to=(22, 18, 23, 22))
    return image


@dataclass
class VaultRecord:
    path: Path
    data: dict

    @property
    def created_at(self) -> str:
        return str(self.data.get("createdAt", ""))

    @property
    def original_name(self) -> str:
        value = self.data.get("originalFileName")
        return str(value) if value else self.path.name

    @property
    def key_file(self) -> str:
        value = self.data.get("keyFile")
        return str(value).strip() if value else ""


@dataclass
class KeyEntry:
    path: str
    vault_count: int
    exists: bool


class VaultManagerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("PII Masker Vault Manager")
        self.icon_image = create_locked_vault_icon()
        self.root.iconphoto(True, self.icon_image)
        self.vault_dir = default_vault_dir()
        self.records: list[VaultRecord] = []
        self.flags: list[BooleanVar] = []
        self.key_entries: list[KeyEntry] = []
        self.key_rows: dict[str, KeyEntry] = {}

        self.status_var = StringVar(value=f"Vault directory: {self.vault_dir}")

        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(frame)
        notebook.grid(row=0, column=0, sticky="nsew")

        vault_tab = ttk.Frame(notebook, padding=8)
        vault_tab.columnconfigure(0, weight=1)
        vault_tab.rowconfigure(1, weight=1)
        notebook.add(vault_tab, text="Vaults")

        keys_tab = ttk.Frame(notebook, padding=8)
        keys_tab.columnconfigure(0, weight=1)
        keys_tab.rowconfigure(1, weight=1)
        notebook.add(keys_tab, text="Keys")

        ttk.Label(vault_tab, text="Saved Document Vaults").grid(row=0, column=0, sticky="w")

        self.canvas = ttk.Frame(vault_tab)
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 6))
        self.canvas.columnconfigure(0, weight=1)
        self.scrollable = ttk.Frame(self.canvas)
        self.scrollable.grid(row=0, column=0, sticky="nsew")
        self.canvas.rowconfigure(0, weight=1)
        self.canvas.columnconfigure(0, weight=1)

        button_row = ttk.Frame(vault_tab)
        button_row.grid(row=2, column=0, sticky="ew", pady=(6, 6))
        button_row.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(button_row, text="Refresh", command=self.reload).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(button_row, text="Select All", command=self.select_all).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(button_row, text="Export ZIPs", command=self.export_selected).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(button_row, text="Delete Selected Vaults", command=self.delete_selected_vaults).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )

        ttk.Label(keys_tab, text="Key Manager").grid(row=0, column=0, sticky="w")

        key_frame = ttk.Frame(keys_tab)
        key_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 6))
        key_frame.columnconfigure(0, weight=1)
        key_frame.rowconfigure(0, weight=1)

        columns = ("path", "vaults", "status")
        self.keys_tree = ttk.Treeview(key_frame, columns=columns, show="headings", height=8)
        self.keys_tree.heading("path", text="Key file path")
        self.keys_tree.heading("vaults", text="Associated vaults")
        self.keys_tree.heading("status", text="File status")
        self.keys_tree.column("path", width=500, anchor="w")
        self.keys_tree.column("vaults", width=140, anchor="center")
        self.keys_tree.column("status", width=130, anchor="center")
        self.keys_tree.grid(row=0, column=0, sticky="nsew")
        self.keys_tree.bind("<<TreeviewSelect>>", self.on_key_selected)

        key_scroll = ttk.Scrollbar(key_frame, orient="vertical", command=self.keys_tree.yview)
        key_scroll.grid(row=0, column=1, sticky="ns")
        self.keys_tree.configure(yscrollcommand=key_scroll.set)

        key_button_row = ttk.Frame(keys_tab)
        key_button_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        key_button_row.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(key_button_row, text="Add Key", command=self.add_key).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(key_button_row, text="Generate Key", command=self.generate_key).grid(row=0, column=1, sticky="ew", padx=3)
        self.delete_key_button = ttk.Button(key_button_row, text="Delete Selected Key", command=self.delete_selected_key)
        self.delete_key_button.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        self.delete_key_button.state(["disabled"])

        ttk.Label(
            keys_tab,
            text="Delete key is enabled only when associated vault count is 0.",
        ).grid(row=3, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.reload()

    def load_records(self) -> list[VaultRecord]:
        if not self.vault_dir.exists():
            return []
        records: list[VaultRecord] = []
        for path in sorted(self.vault_dir.glob("*.vault.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    records.append(VaultRecord(path=path, data=data))
            except Exception:
                continue
        return records

    def clear_rows(self) -> None:
        for child in self.scrollable.winfo_children():
            child.destroy()

    def key_registry_path(self) -> Path:
        return self.vault_dir / "keys.registry.json"

    def normalize_key_path(self, key_path: str) -> str:
        path = Path(key_path).expanduser()
        return str(path.resolve())

    def load_key_registry(self) -> set[str]:
        registry_file = self.key_registry_path()
        if not registry_file.exists():
            return set()
        try:
            payload = json.loads(registry_file.read_text(encoding="utf-8"))
        except Exception:
            return set()
        keys = payload.get("keys")
        if not isinstance(keys, list):
            return set()
        normalized: set[str] = set()
        for item in keys:
            if isinstance(item, str) and item.strip():
                normalized.add(self.normalize_key_path(item))
        return normalized

    def save_key_registry(self, keys: set[str]) -> None:
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        payload = {"keys": sorted(keys)}
        self.key_registry_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def build_key_entries(self) -> list[KeyEntry]:
        vault_counts: dict[str, int] = {}
        for record in self.records:
            if not record.key_file:
                continue
            key_path = self.normalize_key_path(record.key_file)
            vault_counts[key_path] = vault_counts.get(key_path, 0) + 1

        registry_paths = self.load_key_registry()
        all_paths = set(vault_counts.keys()) | registry_paths
        entries: list[KeyEntry] = []
        for key_path in sorted(all_paths):
            key_file = Path(key_path)
            entries.append(
                KeyEntry(
                    path=key_path,
                    vault_count=vault_counts.get(key_path, 0),
                    exists=key_file.exists() and key_file.is_file(),
                )
            )
        return entries

    def reload_keys_table(self) -> None:
        self.key_rows = {}
        for item_id in self.keys_tree.get_children():
            self.keys_tree.delete(item_id)
        self.key_entries = self.build_key_entries()
        for idx, entry in enumerate(self.key_entries):
            item_id = f"key-{idx}"
            self.key_rows[item_id] = entry
            self.keys_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(entry.path, str(entry.vault_count), "Available" if entry.exists else "Missing"),
            )
        self.update_delete_key_button_state()

    def update_delete_key_button_state(self) -> None:
        entry = self.selected_key_entry()
        if entry and entry.vault_count == 0:
            self.delete_key_button.state(["!disabled"])
            return
        self.delete_key_button.state(["disabled"])

    def selected_key_entry(self) -> KeyEntry | None:
        selected = self.keys_tree.selection()
        if not selected:
            return None
        return self.key_rows.get(selected[0])

    def on_key_selected(self, _event: object | None = None) -> None:
        self.update_delete_key_button_state()

    def reload(self) -> None:
        self.records = self.load_records()
        self.flags = [BooleanVar(value=False) for _ in self.records]
        self.clear_rows()
        if not self.records:
            ttk.Label(self.scrollable, text="No vault files found yet.").grid(row=0, column=0, sticky="w")
            self.reload_keys_table()
            self.status_var.set(f"Vault directory: {self.vault_dir} (empty vault list)")
            return
        for idx, record in enumerate(self.records):
            label = f"{record.original_name} | {record.created_at or 'unknown-date'}"
            extra = f"Key: {record.key_file or '(missing)'}"
            row = ttk.Frame(self.scrollable)
            row.grid(row=idx, column=0, sticky="ew", pady=(0, 3))
            row.columnconfigure(1, weight=1)
            ttk.Checkbutton(row, variable=self.flags[idx]).grid(row=0, column=0, sticky="nw")
            ttk.Label(row, text=label).grid(row=0, column=1, sticky="w")
            ttk.Label(row, text=extra).grid(row=1, column=1, sticky="w")
        self.reload_keys_table()
        self.status_var.set(f"Loaded {len(self.records)} vault(s) from {self.vault_dir}")

    def select_all(self) -> None:
        for flag in self.flags:
            flag.set(True)

    def selected_records(self) -> list[VaultRecord]:
        return [record for record, flag in zip(self.records, self.flags) if flag.get()]

    def delete_selected_vaults(self) -> None:
        selected = self.selected_records()
        if not selected:
            messagebox.showerror("Nothing selected", "Select at least one vault.")
            return
        proceed = messagebox.askyesno(
            "Delete selected vaults?",
            f"Delete {len(selected)} selected vault file(s)? This cannot be undone.",
        )
        if not proceed:
            return
        deleted = 0
        errors: list[str] = []
        for record in selected:
            try:
                if record.path.exists():
                    record.path.unlink()
                deleted += 1
            except Exception as exc:
                errors.append(f"{record.path.name}: {exc}")
        self.reload()
        if errors:
            messagebox.showerror("Some vaults were not deleted", "\n".join(errors))
        self.status_var.set(f"Deleted {deleted} vault(s).")

    def add_key(self) -> None:
        selected_file = filedialog.askopenfilename(title="Select key file to manage")
        if not selected_file:
            return
        key_path = Path(selected_file).expanduser()
        if not key_path.exists() or not key_path.is_file():
            messagebox.showerror("Invalid key file", "Selected key path does not exist or is not a file.")
            return
        normalized = self.normalize_key_path(str(key_path))
        registry = self.load_key_registry()
        if normalized in registry:
            messagebox.showinfo("Already added", "This key is already in the key manager.")
            return
        registry.add(normalized)
        self.save_key_registry(registry)
        self.reload()
        self.status_var.set("Added key to key manager.")

    def generate_key(self) -> None:
        suggested = Path.home() / ".pii-masker" / "secret.key"
        selected_file = filedialog.asksaveasfilename(
            title="Generate key file",
            defaultextension=".key",
            initialfile=suggested.name,
            initialdir=str(suggested.parent),
            filetypes=[("Key files", "*.key"), ("All files", "*.*")],
        )
        if not selected_file:
            return

        key_file = Path(selected_file).expanduser()
        key_file.parent.mkdir(parents=True, exist_ok=True)

        command = masker_command(repo_root_dir()) + ["--generate-key", "--key-file", str(key_file)]
        result = subprocess.run(
            command,
            cwd=str(repo_root_dir()),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            messagebox.showerror(
                "Key generation failed",
                f"Command failed with exit code {result.returncode}.\n\n{details}",
            )
            self.status_var.set("Key generation failed.")
            return

        normalized = self.normalize_key_path(str(key_file))
        registry = self.load_key_registry()
        registry.add(normalized)
        self.save_key_registry(registry)
        self.reload()
        self.status_var.set("Generated key and added it to key manager.")

    def delete_selected_key(self) -> None:
        entry = self.selected_key_entry()
        if not entry:
            messagebox.showerror("No key selected", "Select one key row first.")
            return
        if entry.vault_count > 0:
            messagebox.showerror(
                "Key in use",
                f"This key is linked to {entry.vault_count} vault(s). Delete those vaults first.",
            )
            return
        proceed = messagebox.askyesno(
            "Delete selected key?",
            (
                "Delete selected key file from disk and remove it from key manager?\n"
                "This cannot be undone."
            ),
        )
        if not proceed:
            return

        key_file = Path(entry.path)
        registry = self.load_key_registry()
        registry.discard(entry.path)
        self.save_key_registry(registry)

        file_deleted = False
        if key_file.exists() and key_file.is_file():
            try:
                key_file.unlink()
                file_deleted = True
            except Exception as exc:
                messagebox.showerror("Delete failed", f"Could not delete key file:\n{exc}")
                self.reload()
                return

        self.reload()
        if file_deleted:
            self.status_var.set("Deleted key file and removed it from key manager.")
        else:
            self.status_var.set("Removed key from manager (file was already missing).")

    def export_selected(self) -> None:
        selected = self.selected_records()
        if not selected:
            messagebox.showerror("Nothing selected", "Select at least one vault.")
            return

        output_dir = filedialog.askdirectory(title="Choose output folder for ZIP files")
        if not output_dir:
            return
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        vault_zip = output_path / f"selected-vaults-{timestamp}.zip"
        keys_zip = output_path / f"selected-keys-{timestamp}.zip"

        with zipfile.ZipFile(vault_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for record in selected:
                archive.write(record.path, arcname=record.path.name)

        unique_keys: dict[str, tuple[str, bytes]] = {}
        for record in selected:
            key_path = record.key_file
            if not key_path:
                continue
            key_file = Path(key_path).expanduser()
            if not key_file.exists() or not key_file.is_file():
                continue
            content = key_file.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest not in unique_keys:
                unique_keys[digest] = (key_file.name, content)

        if not unique_keys:
            messagebox.showerror("No keys found", "No readable key files were found in selected vaults.")
            return

        with zipfile.ZipFile(keys_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            used_names: set[str] = set()
            for _, (file_name, content) in unique_keys.items():
                candidate = file_name
                suffix = 1
                while candidate in used_names:
                    suffix += 1
                    stem = Path(file_name).stem
                    ext = Path(file_name).suffix
                    candidate = f"{stem}_{suffix}{ext}"
                used_names.add(candidate)
                archive.writestr(candidate, content)

        self.status_var.set(f"Exported {len(selected)} vault(s) and {len(unique_keys)} unique key(s).")
        messagebox.showinfo(
            "Export complete",
            f"Created:\n{vault_zip}\n{keys_zip}",
        )


def main() -> int:
    root = Tk()
    root.geometry("900x520")
    app = VaultManagerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
