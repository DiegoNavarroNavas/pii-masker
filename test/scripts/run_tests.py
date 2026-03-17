#!/usr/bin/env python3
"""
Test Runner for PII Masker

Runs anonymization/deanonymization tests across all preset/language
combinations defined in the test matrix.

Usage:
    python test/scripts/run_tests.py
    python test/scripts/run_tests.py --presets spacy_sm_en stanza_en
    python test/scripts/run_tests.py --languages en de
    python test/scripts/run_tests.py --quick  # Skip slow models
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class TestRunner:
    """Runs PII Masker tests."""

    def __init__(self, config_path: str = "test/config/test_matrix.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.project_root = self._find_project_root()

    def _find_project_root(self) -> Path:
        """Find project root by looking for pii_masker.py."""
        current = Path.cwd()
        while current != current.parent:
            if (current / "pii_masker.py").exists():
                return current
            current = current.parent
        return Path.cwd()

    def _load_config(self) -> dict[str, Any]:
        """Load test matrix configuration."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _get_preset_path(self, preset_name: str) -> Path:
        """Get path to preset file."""
        return self.project_root / "configs" / f"{preset_name}.yaml"

    def _get_input_path(self, lang: str) -> Path:
        """Get path to input file for a language."""
        for lang_info in self.config.get("languages", []):
            if lang_info["code"] == lang:
                return self.project_root / lang_info["input_file"]
        raise ValueError(f"Unknown language: {lang}")

    def _run_command(
        self, cmd: list[str], timeout: int | None = None
    ) -> tuple[int, str, str, float]:
        """Run a command and return (returncode, stdout, stderr, duration)."""
        if timeout is None:
            timeout = self.config.get("settings", {}).get("timeout_seconds", 300)
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
            )
            duration = time.time() - start_time
            return result.returncode, result.stdout, result.stderr, duration
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return -1, "", "Command timed out", duration

    def run_single_test(
        self,
        preset_name: str,
        lang: str,
        output_dir: Path,
        key_file: Path,
    ) -> dict[str, Any]:
        """Run a single test combination."""
        preset_path = self._get_preset_path(preset_name)
        input_path = self._get_input_path(lang)

        test_dir = output_dir / f"{lang}_{preset_name}"
        test_dir.mkdir(parents=True, exist_ok=True)

        # pii_masker appends _masked.txt and _mapping.json to the output base name
        output_base = test_dir / "output"
        masked_file = test_dir / "output_masked.txt"
        mapping_file = test_dir / "output_mapping.json"
        restored_file = test_dir / "restored.txt"
        metrics_file = test_dir / "metrics.json"

        result = {
            "preset": preset_name,
            "language": lang,
            "preset_path": str(preset_path),
            "input_path": str(input_path),
            "output_dir": str(test_dir),
            "success": False,
            "roundtrip_match": False,
            "anonymize_time": 0,
            "deanonymize_time": 0,
            "total_time": 0,
            "error": None,
            "entities_found": 0,
        }

        # Check input exists
        if not input_path.exists():
            result["error"] = f"Input file not found: {input_path}"
            return result

        # Check preset exists
        if not preset_path.exists():
            result["error"] = f"Preset file not found: {preset_path}"
            return result

        # Run anonymization
        anon_cmd = [
            "uv", "run", "python",
            str(self.project_root / "pii_masker.py"),
            "anonymize",
            "-c", str(preset_path),
            "-i", str(input_path),
            "-o", str(output_base),
            "-k", str(key_file),
        ]

        returncode, stdout, stderr, anon_time = self._run_command(anon_cmd)
        result["anonymize_time"] = round(anon_time, 3)

        if returncode != 0:
            result["error"] = f"Anonymization failed: {stderr}"
            return result

        # Count entities from mapping
        if mapping_file.exists():
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                # Handle both old format (flat dict) and new format (with 'mappings' key)
                if "mappings" in mapping:
                    result["entities_found"] = len(mapping["mappings"])
                else:
                    result["entities_found"] = len(mapping)

        # Run deanonymization
        deanon_cmd = [
            "uv", "run", "python",
            str(self.project_root / "pii_masker.py"),
            "deanonymize",
            "-i", str(masked_file),
            "-m", str(mapping_file),
            "-o", str(restored_file),  # deanonymize doesn't add suffix
            "-k", str(key_file),
        ]

        returncode, stdout, stderr, deanon_time = self._run_command(deanon_cmd)
        result["deanonymize_time"] = round(deanon_time, 3)

        if returncode != 0:
            result["error"] = f"Deanonymization failed: {stderr}"
            return result

        # Verify roundtrip
        if self.config.get("settings", {}).get("verify_roundtrip", True):
            with open(input_path, "r", encoding="utf-8") as f:
                original = f.read()
            with open(restored_file, "r", encoding="utf-8") as f:
                restored = f.read()
            result["roundtrip_match"] = original == restored

        result["total_time"] = round(anon_time + deanon_time, 3)
        result["success"] = result["roundtrip_match"] or not self.config.get("settings", {}).get("verify_roundtrip", True)

        # Save metrics
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    def run_tests(
        self,
        presets: list[str] | None = None,
        languages: list[str] | None = None,
        quick: bool = False,
    ) -> dict[str, Any]:
        """Run all tests according to test matrix."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_base = Path(self.config.get("settings", {}).get("output_dir", "test/output"))
        output_dir = self.project_root / output_base / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        key_file = self.project_root / self.config.get("settings", {}).get("key_file", "pii.key")

        # Determine test combinations
        test_matrix = self.config.get("test_matrix", {})

        if presets is None:
            presets = list(test_matrix.keys())

        if quick:
            # Skip slow models (transformers, gliner) in quick mode
            slow_presets = {"xlmr_en", "xlmr_de", "xlmr_fr",
                          "xlmr_it", "xlmr_es",
                          "gliner_en", "gliner_de", "gliner_fr", "gliner_it", "gliner_es"}
            presets = [p for p in presets if p not in slow_presets]

        results = {
            "timestamp": timestamp,
            "config": str(self.config_path),
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tests": [],
        }

        print(f"\n{'='*60}")
        print(f"PII Masker Test Suite")
        print(f"{'='*60}")
        print(f"Output directory: {output_dir}")
        print(f"Key file: {key_file}")
        print(f"Testing {len(presets)} presets...")
        print(f"{'='*60}\n")

        for preset in presets:
            supported_langs = test_matrix.get(preset, [])

            if languages:
                supported_langs = [l for l in supported_langs if l in languages]

            for lang in supported_langs:
                results["total_tests"] += 1
                print(f"[{results['total_tests']}] Testing {preset} with {lang}...", end=" ")

                try:
                    result = self.run_single_test(preset, lang, output_dir, key_file)
                    results["tests"].append(result)

                    if result["success"]:
                        results["passed"] += 1
                        status = "✓ PASSED"
                    else:
                        results["failed"] += 1
                        status = "✗ FAILED"

                    print(f"{status} ({result['total_time']:.2f}s, {result['entities_found']} entities)")

                    if result["error"]:
                        print(f"    Error: {result['error']}")

                except Exception as e:
                    results["failed"] += 1
                    results["tests"].append({
                        "preset": preset,
                        "language": lang,
                        "success": False,
                        "error": str(e),
                    })
                    print(f"✗ ERROR: {e}")

        # Save summary
        summary_file = output_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Print summary
        print(f"\n{'='*60}")
        print(f"Test Summary")
        print(f"{'='*60}")
        print(f"Total:  {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"\nSummary saved to: {summary_file}")
        print(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Run PII Masker tests"
    )
    parser.add_argument(
        "--config",
        default="test/config/test_matrix.yaml",
        help="Path to test matrix config",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        help="Specific presets to test (default: all)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        help="Specific languages to test (default: all)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip slow models (transformers, GLiNER)",
    )

    args = parser.parse_args()

    runner = TestRunner(args.config)
    results = runner.run_tests(
        presets=args.presets,
        languages=args.languages,
        quick=args.quick,
    )

    # Exit with error code if any tests failed
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
