"""Temporary filesystem/lock tests; never invoke privileged OS customization."""
import importlib.util
import json
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_lib import REQUIRED_CHECKS, rename_no_replace, sha256


class OperationSafetyTests(unittest.TestCase):
    def test_atomic_rename_preserves_existing_empty_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, output = root / "stage", root / "candidate"
            stage.mkdir()
            (stage / "fixture").write_text("UNIT TEST")
            output.mkdir()
            identity = output.stat().st_ino
            with self.assertRaises(FileExistsError):
                rename_no_replace(stage, output)
            self.assertEqual(output.stat().st_ino, identity)
            self.assertEqual(list(output.iterdir()), [])
            self.assertTrue(stage.exists())

    def test_atomic_rename_refuses_existing_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "destination"
            source.write_bytes(b"UNIT TEST")
            output.symlink_to(root / "missing")
            with self.assertRaises(FileExistsError):
                rename_no_replace(source, output)
            self.assertTrue(output.is_symlink())
            self.assertTrue(source.exists())

    def test_atomic_rename_fails_closed_if_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source", Path(temporary) / "destination"
            source.mkdir()
            with patch("project_lib.ctypes.CDLL", return_value=object()):
                with self.assertRaises(OSError):
                    rename_no_replace(source, output)
            self.assertTrue(source.exists())
            self.assertFalse(output.exists())

    def test_release_preserves_destination_created_during_staging(self):
        spec = importlib.util.spec_from_file_location("release_fixture", ROOT / "scripts/prepare-release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, report, output = root / "fixture.iso", root / "report.json", root / "candidate"
            image.write_bytes(b"\0" * (16 * 2048 + 1) + b"CD001" + b"UNIT TEST; not bootable")
            report.write_text(json.dumps({
                "schema_version": 1, "tested_iso_sha256": sha256(image),
                "checks": {name: {"status": "pass", "evidence": "UNIT TEST only; no OS tested"}
                           for name in REQUIRED_CHECKS},
            }))
            original_copy = module.shutil.copy2
            identity = []
            def competing_directory(source, destination, *args, **kwargs):
                if Path(source) == image:
                    output.mkdir()
                    identity.append(output.stat().st_ino)
                return original_copy(source, destination, *args, **kwargs)
            with patch.object(module.shutil, "copy2", side_effect=competing_directory), patch.object(
                sys, "argv", ["prepare-release.py", "--iso", str(image),
                              "--test-report", str(report), "--output", str(output)],
            ):
                with self.assertRaises(FileExistsError):
                    module.main()
            self.assertEqual(output.stat().st_ino, identity[0])
            self.assertEqual(list(output.iterdir()), [])
            self.assertEqual(list(root.glob(".release-stage-*")), [])

    def test_customization_lock_blocks_second_operation_and_releases_on_exit(self):
        helper = ROOT / "scripts/customization-lock.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock, marker = root / "target.lock", root / "second-operation"
            holder = subprocess.Popen(
                ["bash", "-c", 'set -euo pipefail; source "$1"; '
                 'acquire_customization_lock "$2"; echo locked; read -r release',
                 "--", str(helper), str(lock)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertTrue(select.select([holder.stdout], [], [], 5)[0], "Lock holder did not become ready")
                self.assertEqual(holder.stdout.readline().strip(), "locked")
                command = ["bash", "-c", 'set -euo pipefail; source "$1"; '
                           'acquire_customization_lock "$2"; printf reached > "$3"',
                           "--", str(helper), str(lock), str(marker)]
                identity = lock.stat().st_ino
                competing = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertNotEqual(competing.returncode, 0)
                self.assertIn("already being customized", competing.stderr)
                self.assertFalse(marker.exists())
                holder.communicate("\n", timeout=5)
                self.assertEqual(holder.returncode, 0)
                retry = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual(retry.returncode, 0, retry.stderr)
                self.assertEqual(marker.read_text(), "reached")
                self.assertEqual(lock.stat().st_ino, identity)
            finally:
                if holder.poll() is None:
                    holder.kill()
                holder.communicate(timeout=5)

    def test_customization_lock_precedes_policy_backup(self):
        script = (ROOT / "scripts/apply-in-cubic.sh").read_text()
        self.assertLess(
            script.index("acquire_customization_lock /usr/share/desktop-os/.customization.lock"),
            script.index("POLICY=/usr/sbin/policy-rc.d"),
        )


if __name__ == "__main__":
    unittest.main()