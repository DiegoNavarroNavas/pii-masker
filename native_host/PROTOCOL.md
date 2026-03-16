# Native Messaging Protocol (v1)

This protocol is used between the Chrome extension and the native host.

## Request

The extension sends one JSON object:

```json
{
  "version": 1,
  "action": "redact_upload",
  "jobId": "uuid-string",
  "fileName": "document.pdf",
  "mimeType": "application/pdf",
  "contentBase64": "base64-encoded-file-bytes",
  "language": "en",
  "keyFile": "C:/path/to/secret.key",
  "engine": "spacy",
  "model": "en_core_web_lg",
  "spacyModel": "en_core_web_lg",
  "transformersModel": "Babelscape/wikineural-multilingual-ner",
  "localEncoderModel": "answerdotai/ModernBERT-base",
  "minHostVersion": "0.2.0",
  "includeMapping": false
}
```

`model`, `spacyModel`, `transformersModel`, `localEncoderModel`, and `minHostVersion` are optional. The extension sends `model` resolved from the selected engine plus engine-specific fields. `minHostVersion` is used by newer extension builds to enforce companion-app compatibility.

## Success Response

```json
{
  "ok": true,
  "status": "ok",
  "jobId": "uuid-string",
  "hostVersion": "0.2.0",
  "fileName": "document.redacted.pdf",
  "mimeType": "application/pdf",
  "contentBase64": "base64-encoded-redacted-bytes",
  "mapping": {}
}
```

`mapping` is returned only when `includeMapping` is true.

## Error Response

```json
{
  "ok": false,
  "status": "error",
  "jobId": "uuid-string",
  "hostVersion": "0.2.0",
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Only PDF and text formats are supported."
  }
}
```

## Error Codes

- `INVALID_REQUEST`: Missing or invalid protocol fields.
- `INVALID_BASE64`: `contentBase64` cannot be decoded.
- `REQUEST_TOO_LARGE`: Payload exceeds host size limit.
- `UNSUPPORTED_FILE_TYPE`: Unsupported extension/MIME type.
- `UNSUPPORTED_TEXT_ENCODING`: Text file is not UTF-8 decodable.
- `DEPENDENCY_MISSING`: PDF support dependency missing locally.
- `HOST_VERSION_UNSUPPORTED`: Native host is older than extension-required minimum.
- `MASKER_COMMAND_FAILED`: `pii_masker.py` call failed.
- `MASKER_TIMEOUT`: `pii_masker.py` call timed out.
- `INTERNAL_ERROR`: Unexpected host error.

## Notes

- All data remains local: extension <-> native host <-> local masker process.
- Native host executes `uv run python pii_masker.py --json-mode` by default.
- The command can be overridden by setting `PII_MASKER_CMD`.
