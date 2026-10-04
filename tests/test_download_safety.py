"""Mocked download fixtures only: no network, real signing, or OS image testing."""
import contextlib
import hashlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_lib import KEY_FINGERPRINT


class DownloadSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="download-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = b"UNIT TEST download fixture; not an OS image"
        self.base = {
            "filename": "fixture.iso", "release_url": "https://example.invalid/",
            "sha256": hashlib.sha256(self.data).hexdigest(),
        }
        self.target = self.root / "build/base/fixture.iso"
        self.partial = self.target.with_suffix(".iso.part")
        spec = importlib.util.spec_from_file_location("fetch_base_fixture", ROOT / "scripts/fetch-base.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for mock in (
            patch.object(self.module, "ROOT", self.root),
            patch.object(self.module, "load_config", return_value={"base": self.base}),
            patch.object(self.module.shutil, "which", return_value="/fixture/gpg"),
            patch.object(self.module.shutil, "disk_usage", return_value=SimpleNamespace(free=2 * 1024**3)),
            patch.object(self.module, "fetch_small", side_effect=self.metadata),
            patch.object(self.module.subprocess, "run", return_value=SimpleNamespace(
                stdout="[GNUPG:] VALIDSIG " + KEY_FINGERPRINT, returncode=0,
            )),
            patch.object(sys, "argv", ["fetch-base.py"]),
            patch("builtins.print"),
        ):
            self.patches.enter_context(mock)

    def metadata(self, url, destination):
        destination.write_text(
            self.base["sha256"] + " *fixture.iso\n"
            if destination.name == "SHA256SUMS" else "UNIT TEST metadata fixture"
        )

    def response(self, content=None):
        response = io.BytesIO(self.data if content is None else content)
        response.headers = {"Content-Length": str(len(self.data))}
        return response

    def test_exclusive_creation_failure_preserves_competing_download(self):
        def competing_download(*args, **kwargs):
            self.partial.write_bytes(b"other process download")
            return self.response()
        with patch.object(self.module.urllib.request, "urlopen", side_effect=competing_download):
            with self.assertRaises(FileExistsError):
                self.module.main()
        self.assertEqual(self.partial.read_bytes(), b"other process download")

    def test_connection_failure_preserves_competing_download(self):
        def connection_failure(*args, **kwargs):
            self.partial.write_bytes(b"other process download")
            raise OSError("UNIT TEST connection failure")
        with patch.object(self.module.urllib.request, "urlopen", side_effect=connection_failure):
            with self.assertRaises(OSError):
                self.module.main()
        self.assertEqual(self.partial.read_bytes(), b"other process download")

    def test_incomplete_owned_download_is_cleaned_up(self):
        with patch.object(self.module.urllib.request, "urlopen", return_value=self.response(b"short")):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                self.module.main()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.target.exists())

    def test_successful_download_is_verified_and_finalized(self):
        with patch.object(self.module.urllib.request, "urlopen", return_value=self.response()):
            self.module.main()
        self.assertEqual(self.target.read_bytes(), self.data)
        self.assertFalse(self.partial.exists())

    def test_finalization_preserves_destination_created_during_download(self):
        def competing_destination(*args, **kwargs):
            self.target.write_bytes(b"other process image")
            return self.response()
        with patch.object(self.module.urllib.request, "urlopen", side_effect=competing_destination):
            with self.assertRaises(FileExistsError):
                self.module.main()
        self.assertEqual(self.target.read_bytes(), b"other process image")
        self.assertFalse(self.partial.exists())

    def test_preexisting_partial_is_preserved_without_requesting_image(self):
        self.partial.parent.mkdir(parents=True)
        self.partial.write_bytes(b"previous unfinished download")
        with patch.object(self.module.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "Incomplete download exists"):
                self.module.main()
        request.assert_not_called()
        self.assertEqual(self.partial.read_bytes(), b"previous unfinished download")

    def test_interrupted_owned_download_is_cleaned_and_can_be_retried(self):
        response = self.response()
        with patch.object(response, "read", side_effect=[self.data[:5], KeyboardInterrupt()]):
            with patch.object(self.module.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(KeyboardInterrupt):
                    self.module.main()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.target.exists())
        with patch.object(self.module.urllib.request, "urlopen", return_value=self.response()):
            self.module.main()
        self.assertEqual(self.target.read_bytes(), self.data)
        self.assertFalse(self.partial.exists())

    def test_interrupt_before_exclusive_creation_preserves_competing_download(self):
        def interrupted_connection(*args, **kwargs):
            self.partial.write_bytes(b"other process download")
            raise KeyboardInterrupt()
        with patch.object(self.module.urllib.request, "urlopen", side_effect=interrupted_connection):
            with self.assertRaises(KeyboardInterrupt):
                self.module.main()
        self.assertEqual(self.partial.read_bytes(), b"other process download")
        self.assertFalse(self.target.exists())

    def test_interrupt_during_verification_cleans_owned_partial(self):
        with patch.object(self.module.urllib.request, "urlopen", return_value=self.response()):
            with patch.object(self.module, "sha256", side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    self.module.main()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.target.exists())

    def test_cli_interrupt_returns_130_without_traceback(self):
        with patch.object(self.module, "main", side_effect=KeyboardInterrupt()):
            self.assertEqual(self.module.cli(), 130)


if __name__ == "__main__":
    unittest.main()