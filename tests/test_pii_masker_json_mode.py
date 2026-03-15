import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class PiiMaskerJsonModeTests(unittest.TestCase):
    def run_json_mode(self, payload_text: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "pii_masker.py", "--json-mode"],
            cwd=REPO_ROOT,
            input=payload_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_empty_request(self):
        proc = self.run_json_mode("")
        self.assertEqual(proc.returncode, 2)
        body = json.loads(proc.stdout)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "EMPTY_REQUEST")

    def test_invalid_json(self):
        proc = self.run_json_mode("{")
        self.assertEqual(proc.returncode, 2)
        body = json.loads(proc.stdout)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_JSON")

    def test_invalid_action(self):
        payload = json.dumps({"action": "nope", "key_file": "x"})
        proc = self.run_json_mode(payload)
        self.assertEqual(proc.returncode, 2)
        body = json.loads(proc.stdout)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_ACTION")


if __name__ == "__main__":
    unittest.main()
