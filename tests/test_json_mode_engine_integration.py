import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
RUN_ENGINE_INTEGRATION = "--run-engine-integration" in sys.argv
RUN_HEAVY_ENGINE = "--run-heavy-engine" in sys.argv

# Remove custom flags so unittest argument parsing does not fail.
for _flag in ("--run-engine-integration", "--run-heavy-engine"):
    while _flag in sys.argv:
        sys.argv.remove(_flag)


def _python_cmd() -> str:
    if PYTHON_EXE.exists():
        return str(PYTHON_EXE)
    return sys.executable


@unittest.skipUnless(
    RUN_ENGINE_INTEGRATION,
    "Use --run-engine-integration to run real engine integration tests.",
)
class JsonModeEngineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.key_file = Path(cls.temp_dir.name) / "integration_test.key"
        proc = subprocess.run(
            [_python_cmd(), "pii_masker.py", "--generate-key", "--key-file", str(cls.key_file)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to generate integration key. rc={proc.returncode} stderr={proc.stderr}"
            )

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def run_json_mode(self, payload: dict, timeout: int = 300) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [_python_cmd(), "pii_masker.py", "--json-mode"],
            cwd=REPO_ROOT,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )

    def assert_engine_ok(self, engine: str, extra_payload: dict | None = None):
        payload = {
            "action": "anonymize",
            "text": "John lives in Berlin.",
            "language": "en",
            "engine": engine,
            "key_file": str(self.key_file),
        }
        if extra_payload:
            payload.update(extra_payload)

        proc = self.run_json_mode(payload)
        self.assertEqual(proc.returncode, 0, msg=f"{engine} failed rc={proc.returncode} stderr={proc.stderr}")

        body = json.loads(proc.stdout)
        if not body.get("ok"):
            self.fail(f"{engine} returned error payload: {body}")
        self.assertIn("masked_text", body)
        self.assertIn("mapping", body)

    def test_spacy_engine_anonymize(self):
        self.assert_engine_ok("spacy")

    def test_stanza_engine_anonymize_dependency_path_resolved(self):
        """
        Ensures the previously failing path is actually fixed:
        stanza must run, not return DEPENDENCY_OR_ENGINE_ERROR.
        """
        payload = {
            "action": "anonymize",
            "text": "John lives in Berlin.",
            "language": "en",
            "engine": "stanza",
            "key_file": str(self.key_file),
        }
        proc = self.run_json_mode(payload, timeout=420)
        self.assertEqual(proc.returncode, 0, msg=f"stanza rc={proc.returncode} stderr={proc.stderr}")
        body = json.loads(proc.stdout)
        self.assertTrue(body.get("ok"), msg=f"stanza returned non-ok payload: {body}")
        error = body.get("error", {})
        self.assertNotEqual(error.get("code"), "DEPENDENCY_OR_ENGINE_ERROR")


@unittest.skipUnless(
    RUN_HEAVY_ENGINE,
    "Use --run-heavy-engine to include transformers integration tests.",
)
class JsonModeTransformersIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.key_file = Path(cls.temp_dir.name) / "integration_test.key"
        proc = subprocess.run(
            [_python_cmd(), "pii_masker.py", "--generate-key", "--key-file", str(cls.key_file)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to generate integration key. rc={proc.returncode} stderr={proc.stderr}"
            )

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_transformers_engine_anonymize(self):
        payload = {
            "action": "anonymize",
            "text": "John lives in Berlin.",
            "language": "en",
            "engine": "transformers",
            "spacy_model": "en_core_web_sm",
            "transformer_model": "Babelscape/wikineural-multilingual-ner",
            "key_file": str(self.key_file),
        }
        proc = subprocess.run(
            [_python_cmd(), "pii_masker.py", "--json-mode"],
            cwd=REPO_ROOT,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            timeout=900,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"transformers failed rc={proc.returncode} stderr={proc.stderr}",
        )
        body = json.loads(proc.stdout)
        self.assertTrue(body.get("ok"), msg=f"transformers returned non-ok payload: {body}")


if __name__ == "__main__":
    unittest.main()
