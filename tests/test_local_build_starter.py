"""Mock the external-host controller; never install packages or launch a GUI."""
import contextlib
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class LocalBuildStarterTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("local_starter_fixture", ROOT / "scripts/prepare-local-build.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.host = {
            "id": "ubuntu", "version": "24.04", "architecture": "x86_64",
            "workspace": False, "desktop": True, "free_gib": 40,
        }
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(self.module, "host_info", return_value=self.host))
        stack.enter_context(patch.object(self.module.os, "geteuid", return_value=1000))
        self.run = stack.enter_context(patch.object(
            self.module.subprocess, "run", return_value=SimpleNamespace(stdout="0\n", returncode=0),
        ))
        self.confirm = stack.enter_context(patch("builtins.input", return_value="BUILD"))
        stack.enter_context(patch("builtins.print"))

    def invoke(self, flag):
        with patch.object(sys, "argv", ["prepare-local-build.py", flag]):
            self.module.main()

    def test_check_is_read_only(self):
        self.invoke("--check")
        self.run.assert_not_called()
        self.confirm.assert_not_called()

    def test_workspace_is_rejected_before_any_commands(self):
        self.host["workspace"] = True
        with self.assertRaisesRegex(ValueError, "not in the Replit"):
            self.invoke("--prepare-local-build")
        self.run.assert_not_called()
        self.confirm.assert_not_called()

    def test_unsupported_host_is_rejected(self):
        for key, value in (("id", "debian"), ("architecture", "aarch64"), ("desktop", False)):
            original = self.host[key]
            self.host[key] = value
            with self.assertRaises(ValueError):
                self.invoke("--prepare-local-build")
            self.host[key] = original
        self.run.assert_not_called()

    def test_declined_risk_confirmation_changes_nothing(self):
        self.confirm.return_value = "NO"
        with self.assertRaisesRegex(ValueError, "Cancelled"):
            self.invoke("--prepare-local-build")
        self.run.assert_not_called()

    def test_sudo_wrapper_cannot_trigger_package_installation(self):
        self.run.return_value.stdout = "1000\n"
        with self.assertRaisesRegex(ValueError, "does not grant administrator"):
            self.invoke("--prepare-local-build")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(commands, [["sudo", "-v"], ["sudo", "-n", "id", "-u"]])

    def test_preparation_checks_identity_before_install_and_launches_only_cubic(self):
        self.invoke("--prepare-local-build")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(commands[:2], [["sudo", "-v"], ["sudo", "-n", "id", "-u"]])
        self.assertIn(["sudo", "apt-add-repository", "--yes", self.module.PPA], commands)
        self.assertIn([sys.executable, str(ROOT / "scripts/fetch-base.py")], commands)
        self.assertEqual(commands[-1], ["cubic"])
        self.assertFalse(any("mkfs" in part or part == "dd" for command in commands for part in command))

    def test_recipe_failure_stops_before_package_changes(self):
        def fail_recipe(command, **kwargs):
            if str(ROOT / "scripts/check-project.py") in command:
                raise self.module.subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout="0\n", returncode=0)
        self.run.side_effect = fail_recipe
        with self.assertRaises(self.module.subprocess.CalledProcessError):
            self.invoke("--prepare-local-build")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertFalse(any("apt-get" in command or "apt-add-repository" in command for command in commands))

    def test_cancelled_confirmation_returns_130_without_host_changes(self):
        self.confirm.side_effect = KeyboardInterrupt()
        with patch.object(sys, "argv", ["prepare-local-build.py", "--prepare-local-build"]):
            self.assertEqual(self.module.cli(), 130)
        self.run.assert_not_called()

    def test_interrupted_download_prevents_cubic_launch(self):
        def interrupt_download(command, **kwargs):
            if str(ROOT / "scripts/fetch-base.py") in command:
                raise KeyboardInterrupt()
            return SimpleNamespace(stdout="0\n", returncode=0)
        self.run.side_effect = interrupt_download
        with patch.object(sys, "argv", ["prepare-local-build.py", "--prepare-local-build"]):
            self.assertEqual(self.module.cli(), 130)
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertNotIn(["cubic"], commands)


if __name__ == "__main__":
    unittest.main()