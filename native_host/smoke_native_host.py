#!/usr/bin/env python3
"""
CLI smoke test for Native Messaging host without browser clicks.
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
import subprocess
import sys
from pathlib import Path


def read_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def run_native_request(host_path: str, payload: dict) -> dict:
    proc = subprocess.Popen(
        [host_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    request_bytes = json.dumps(payload).encode("utf-8")
    framed = struct.pack("<I", len(request_bytes)) + request_bytes
    assert proc.stdin is not None
    proc.stdin.write(framed)
    proc.stdin.flush()
    proc.stdin.close()

    assert proc.stdout is not None
    length_raw = proc.stdout.read(4)
    if len(length_raw) != 4:
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        raise RuntimeError(f"No framed response from host. stderr={stderr}")
    length = struct.unpack("<I", length_raw)[0]
    body = proc.stdout.read(length).decode("utf-8", errors="replace")
    return json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test native messaging host")
    parser.add_argument("--manifest", required=True, help="Path to installed host manifest JSON")
    parser.add_argument("--key-file", required=True, help="Path to encryption key")
    parser.add_argument("--input-file", required=True, help="Input file to redact")
    parser.add_argument("--language", default="en", help="Language code")
    parser.add_argument("--engine", default="spacy", help="Engine name")
    args = parser.parse_args()

    manifest = read_manifest(Path(args.manifest))
    host_path = manifest["path"]
    in_path = Path(args.input_file)
    mime = "application/pdf" if in_path.suffix.lower() == ".pdf" else "text/plain"
    payload = {
        "version": 1,
        "action": "redact_upload",
        "jobId": "smoke-test",
        "fileName": in_path.name,
        "mimeType": mime,
        "contentBase64": base64.b64encode(in_path.read_bytes()).decode("ascii"),
        "language": args.language,
        "engine": args.engine,
        "keyFile": args.key_file,
        "includeMapping": False,
    }
    response = run_native_request(host_path, payload)
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
