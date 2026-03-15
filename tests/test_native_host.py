import base64
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from native_host.host import (
    MAX_REQUEST_BYTES,
    is_pdf,
    is_text_file,
    parse_request,
    process_request,
    run_masker_text,
)


class NativeHostProtocolTests(unittest.TestCase):
    def test_parse_request_ok(self):
        payload = {
            "action": "redact_upload",
            "jobId": "job-1",
            "fileName": "a.txt",
            "mimeType": "text/plain",
            "contentBase64": base64.b64encode(b"hello").decode("ascii"),
            "keyFile": "secret.key",
        }
        parsed, error = parse_request(payload)
        self.assertIsNone(error)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["jobId"], "job-1")
        self.assertEqual(parsed["fileName"], "a.txt")
        self.assertEqual(parsed["contentBytes"], b"hello")

    def test_parse_request_missing_field(self):
        parsed, error = parse_request({"action": "redact_upload"})
        self.assertIsNone(parsed)
        self.assertEqual(error["error"]["code"], "INVALID_REQUEST")

    def test_parse_request_invalid_base64(self):
        payload = {
            "action": "redact_upload",
            "jobId": "job-2",
            "fileName": "a.txt",
            "mimeType": "text/plain",
            "contentBase64": "$$$",
            "keyFile": "secret.key",
        }
        parsed, error = parse_request(payload)
        self.assertIsNone(parsed)
        self.assertEqual(error["error"]["code"], "INVALID_BASE64")

    def test_parse_request_too_large(self):
        huge = b"a" * (MAX_REQUEST_BYTES + 1)
        payload = {
            "action": "redact_upload",
            "jobId": "job-3",
            "fileName": "a.txt",
            "mimeType": "text/plain",
            "contentBase64": base64.b64encode(huge).decode("ascii"),
            "keyFile": "secret.key",
        }
        parsed, error = parse_request(payload)
        self.assertIsNone(parsed)
        self.assertEqual(error["error"]["code"], "REQUEST_TOO_LARGE")

    def test_file_type_helpers(self):
        self.assertTrue(is_text_file("note.md", "text/markdown"))
        self.assertTrue(is_text_file("data.bin", "text/plain"))
        self.assertFalse(is_text_file("archive.zip", "application/zip"))
        self.assertTrue(is_pdf("paper.pdf", "application/octet-stream"))
        self.assertTrue(is_pdf("paper.bin", "application/pdf"))
        self.assertFalse(is_pdf("paper.txt", "text/plain"))

    def test_parse_request_with_all_optional_fields(self):
        payload = {
            "action": "redact_upload",
            "jobId": "job-opts",
            "fileName": "a.txt",
            "mimeType": "text/plain",
            "contentBase64": base64.b64encode(b"hello").decode("ascii"),
            "keyFile": "secret.key",
            "language": "de",
            "engine": "transformers",
            "model": "de_core_news_sm:dslim/bert-base-NER",
            "spacyModel": "de_core_news_sm",
            "transformersModel": "dslim/bert-base-NER",
            "localEncoderModel": "answerdotai/ModernBERT-base",
            "includeMapping": True,
        }
        parsed, error = parse_request(payload)
        self.assertIsNone(error)
        assert parsed is not None
        self.assertEqual(parsed["language"], "de")
        self.assertEqual(parsed["engine"], "transformers")
        self.assertEqual(parsed["model"], "de_core_news_sm:dslim/bert-base-NER")
        self.assertEqual(parsed["spacyModel"], "de_core_news_sm")
        self.assertEqual(parsed["transformersModel"], "dslim/bert-base-NER")
        self.assertEqual(parsed["localEncoderModel"], "answerdotai/ModernBERT-base")
        self.assertTrue(parsed["includeMapping"])

    @patch("native_host.host.run_command_with_live_stderr")
    def test_run_masker_text_sends_all_engine_options(self, mock_run_command):
        mock_run_command.return_value = (
            0,
            json.dumps(
            {"ok": True, "masked_text": "<PERSON_1>", "mapping": {"<PERSON_1>": ["PERSON", "enc"]}}
            ),
            "",
        )

        masked_text, mapping = run_masker_text(
            repo_root=Path("."),
            text="John",
            language="de",
            key_file="secret.key",
            engine="transformers",
            model="de_core_news_sm:dslim/bert-base-NER",
            spacy_model="de_core_news_sm",
            transformer_model="dslim/bert-base-NER",
        )
        self.assertEqual(masked_text, "<PERSON_1>")
        self.assertIn("<PERSON_1>", mapping)

        call_kwargs = mock_run_command.call_args.kwargs
        sent_payload = json.loads(call_kwargs["stdin_text"])
        self.assertEqual(call_kwargs["command"], [".venv\\Scripts\\python.exe", "pii_masker.py", "--json-mode"])
        self.assertEqual(sent_payload["engine"], "transformers")
        self.assertEqual(sent_payload["model"], "de_core_news_sm:dslim/bert-base-NER")
        self.assertEqual(sent_payload["spacy_model"], "de_core_news_sm")
        self.assertEqual(sent_payload["transformer_model"], "dslim/bert-base-NER")

    @patch("native_host.host.run_command_with_live_stderr")
    def test_run_masker_text_surfaces_dependency_error(self, mock_run_command):
        mock_run_command.return_value = (
            6,
            json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "DEPENDENCY_OR_ENGINE_ERROR",
                    "message": "NLP engine initialization failed. Check dependencies/models.",
                },
            }
            ),
            "Missing dependencies for engine 'stanza'",
        )

        with self.assertRaises(ModuleNotFoundError):
            run_masker_text(
                repo_root=Path("."),
                text="John",
                language="en",
                key_file="secret.key",
                engine="stanza",
                model=None,
                spacy_model=None,
                transformer_model=None,
            )

    @patch("native_host.host.redact_text_file")
    def test_process_request_mapping_toggle(self, mock_redact_text_file):
        mock_redact_text_file.return_value = (b"masked", {"<PERSON_1>": ["PERSON", "enc"]})
        repo_root = Path(".")
        base = {
            "action": "redact_upload",
            "jobId": "job-map",
            "fileName": "a.txt",
            "mimeType": "text/plain",
            "contentBase64": base64.b64encode(b"hello").decode("ascii"),
            "keyFile": "secret.key",
        }

        response_without = process_request(repo_root, dict(base, includeMapping=False))
        self.assertTrue(response_without["ok"])
        self.assertNotIn("mapping", response_without)

        response_with = process_request(repo_root, dict(base, includeMapping=True))
        self.assertTrue(response_with["ok"])
        self.assertIn("mapping", response_with)
        self.assertEqual(response_with["mapping"]["<PERSON_1>"][0], "PERSON")


if __name__ == "__main__":
    unittest.main()
