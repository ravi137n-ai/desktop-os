import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_lib import (
    KEY_FINGERPRINT, REQUIRED_CHECKS, load_config, parse_checksums,
    read_packages, sha256, validate_report, validate_signature_status,
)


class RecipeTests(unittest.TestCase):
    def test_real_project_validates(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check-project.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_configuration_is_pinned(self):
        base = load_config()["base"]
        self.assertEqual(base["architecture"], "amd64")
        self.assertEqual(base["signing_key_fingerprint"], KEY_FINGERPRINT)

    def test_package_list(self):
        self.assertIn("libreoffice-writer", read_packages(ROOT / "config/packages.txt"))

    def test_package_injection_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "packages"
            for value in ("--allow-unauthenticated\n", "vlc;whoami\n", "vlc\nvlc\n"):
                path.write_text(value)
                with self.assertRaises(ValueError):
                    read_packages(path)

    def test_checksums_parse(self):
        self.assertEqual(parse_checksums("a" * 64 + " *base.iso\n"), {"base.iso": "a" * 64})

    def test_unsafe_checksum_entries_rejected(self):
        for name in ("../base.iso", "/base.iso", "base.iso;rm"):
            with self.assertRaises(ValueError):
                parse_checksums("a" * 64 + " *" + name)

    def test_duplicate_checksum_entries_rejected(self):
        with self.assertRaises(ValueError):
            parse_checksums(("a" * 64 + " *base.iso\n") * 2)

    def test_pinned_signature_status(self):
        validate_signature_status("[GNUPG:] VALIDSIG " + KEY_FINGERPRINT + " 2026-01-01 0")

    def test_wrong_signature_rejected(self):
        with self.assertRaises(ValueError):
            validate_signature_status("[GNUPG:] VALIDSIG " + "A" * 40)

    def test_valid_pinned_signature_with_unknown_legacy_key(self):
        validate_signature_status("[GNUPG:] VALIDSIG " + KEY_FINGERPRINT + "\n[GNUPG:] NO_PUBKEY 46181433FBB75451")

    def test_invalid_signature_rejected(self):
        for code in ("BADSIG", "REVKEYSIG", "EXPKEYSIG", "EXPSIG"):
            with self.assertRaises(ValueError):
                validate_signature_status("[GNUPG:] VALIDSIG " + KEY_FINGERPRINT + "\n[GNUPG:] " + code)

    def test_streamed_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample"
            path.write_bytes(b"source-fixture")
            self.assertEqual(sha256(path), hashlib.sha256(b"source-fixture").hexdigest())

    def test_pending_report_cannot_release(self):
        template = json.loads((ROOT / "config/test-report.template.json").read_text())
        with self.assertRaises(ValueError):
            validate_report(template, "a" * 64)

    def test_report_must_match_exact_image(self):
        report = {"schema_version": 1, "tested_iso_sha256": "a" * 64,
                  "checks": {name: {"status": "pass", "evidence": "Test fixture only"} for name in REQUIRED_CHECKS}}
        validate_report(report, "a" * 64)
        with self.assertRaises(ValueError):
            validate_report(report, "b" * 64)
        incomplete = copy.deepcopy(report)
        incomplete["checks"]["vm_installation"]["evidence"] = ""
        with self.assertRaises(ValueError):
            validate_report(incomplete, "a" * 64)

    def test_apply_requires_explicit_intent(self):
        result = subprocess.run(["bash", str(ROOT / "scripts/apply-in-cubic.sh")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stderr)

    def test_malformed_report_rejected(self):
        for report in ([], {"schema_version": 1, "tested_iso_sha256": "a" * 64, "checks": []}):
            with self.assertRaises(ValueError):
                validate_report(report, "a" * 64)

    def test_release_rejects_non_iso(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            fake = temp / "fake.iso"
            fake.write_bytes(b"not an ISO")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/prepare-release.py"),
                "--iso", str(fake), "--test-report", str(ROOT / "config/test-report.template.json"),
                "--output", str(temp / "release"),
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((temp / "release").exists())

    def test_release_staging_and_overwrite_protection(self):
        # Structural fixture ONLY: it is not a bootable OS. This exercises local
        # file staging and checksums, not the truth of manual test evidence.
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            image = temp / "structural-fixture.iso"
            image.write_bytes(b"\0" * (16 * 2048 + 1) + b"CD001" + b"\0" * 2048)
            digest = sha256(image)
            report = temp / "fixture-report.json"
            report.write_text(json.dumps({
                "schema_version": 1, "tested_iso_sha256": digest,
                "checks": {name: {"status": "pass", "evidence": "UNIT TEST fixture; no OS tested"} for name in REQUIRED_CHECKS},
            }))
            output = temp / "candidate"
            command = [
                sys.executable, str(ROOT / "scripts/prepare-release.py"),
                "--iso", str(image), "--test-report", str(report), "--output", str(output),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "release.json").read_text())
            self.assertEqual(manifest["status"], "locally-staged-candidate-not-published")
            self.assertEqual(sha256(output / manifest["filename"]), digest)
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("already exists", again.stderr)


if __name__ == "__main__":
    unittest.main()