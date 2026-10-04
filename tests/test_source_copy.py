"""Exercise documented source-only tar commands in disposable local fixtures."""
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def documented_command(path):
    match = re.search(r"```sh\n(mkdir -p build\n.*?)\n```", path.read_text(), re.DOTALL)
    if not match:
        raise AssertionError(f"Source-copy command missing from {path}")
    return match.group(1)


class SourceCopyTests(unittest.TestCase):
    def test_readme_and_build_guide_commands_agree(self):
        self.assertEqual(documented_command(ROOT / "README.md"), documented_command(ROOT / "docs/BUILD.md"))

    def test_transfer_excludes_generated_files_and_remains_valid_source(self):
        with tempfile.TemporaryDirectory(prefix="source-copy-test-") as directory:
            fixture = Path(directory) / "source"
            shutil.copytree(ROOT, fixture, ignore=shutil.ignore_patterns(
                "build", "dist", ".git", "__pycache__", "*.pyc", "*.pyo",
            ))
            excluded = (
                "build/base/fixture.iso", "dist/candidate/fixture.iso",
                ".git/config", "scripts/.git/config",
                "scripts/__pycache__/fixture.pyc", "scripts/fixture.pyo",
                "tests/.pytest_cache/cache", "scripts/.mypy_cache/cache",
                "scripts/.ruff_cache/cache",
            )
            for name in excluded:
                file = fixture / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("UNIT TEST exclusion fixture, not an OS image or credential.")
            subprocess.run(["bash", "-e", "-c", documented_command(ROOT / "docs/BUILD.md")],
                           cwd=fixture, check=True, capture_output=True)
            archive = fixture / "build/ubuntu-desktop-source.tar.gz"
            with tarfile.open(archive) as bundle:
                members = bundle.getmembers()
                names = {member.name for member in members}
                for name in excluded:
                    self.assertNotIn("ubuntu-desktop/" + name, names)
                self.assertIn("ubuntu-desktop/project.json", names)
                self.assertIn("ubuntu-desktop/scripts/apply-in-cubic.sh", names)
                self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))
            extracted = Path(directory) / "extracted"
            extracted.mkdir()
            subprocess.run(["tar", "-xzf", str(archive), "-C", str(extracted)], check=True)
            source = extracted / "ubuntu-desktop"
            subprocess.run(["python3", str(source / "scripts/check-project.py")],
                           cwd=source, check=True, capture_output=True)
            self.assertFalse((source / "build").exists())
            self.assertFalse((source / "dist").exists())


if __name__ == "__main__":
    unittest.main()