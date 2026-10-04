#!/usr/bin/env python3
"""Prepare an isolated Ubuntu desktop build host; Cubic still generates the ISO."""
import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PPA = "ppa:cubic-wizard/release"


def host_info():
    fields = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            fields[key] = value.strip().strip('"')
    return {
        "id": fields.get("ID", ""),
        "version": fields.get("VERSION_ID", ""),
        "architecture": platform.machine(),
        "workspace": bool(os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN")),
        "desktop": bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
        "free_gib": shutil.disk_usage(ROOT).free / 1024**3,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check the local host without changing it.")
    mode.add_argument("--prepare-local-build", action="store_true", help="Confirm isolated-host risk, install tools, download the base, and open Cubic.")
    args = parser.parse_args()
    host = host_info()
    if host["workspace"]:
        raise ValueError("Run this on your isolated Ubuntu desktop build computer, not in the Replit workspace.")
    if host["id"] != "ubuntu" or host["architecture"] != "x86_64":
        raise ValueError("This starter requires an Ubuntu x86-64 build computer.")
    if not host["version"] or int(host["version"].split(".")[0]) < 20:
        raise ValueError("This starter requires Ubuntu 20.04 or later with Python 3.8 or later.")
    if not host["desktop"]:
        raise ValueError("A desktop session is required to open Cubic's interactive wizard.")
    print(f"Build host: Ubuntu {host['version']}, {host['architecture']}; {host['free_gib']:.1f} GiB free.")
    print("Recommended: roughly 40 GB free storage and 8 GB RAM; actual build needs are not yet measured.")
    if args.check:
        print("Read-only host check complete. No tools installed, image downloaded, or ISO built.")
        return
    if os.geteuid() == 0:
        raise ValueError("Run this as your normal desktop user; individual package commands use sudo.")
    print(
        "Cubic's official installation guide warns that privileged components may "
        "be exploited without a root password. Use an isolated build machine or VM, "
        "not your everyday computer. This adds Cubic's third-party PPA and installs "
        "build tools on the host, not in the resulting image."
    )
    print("Review: https://github.com/PJ-Singh-001/Cubic/wiki/Install-Cubic")
    if input("Type BUILD to confirm the isolated-host risk and continue: ").strip() != "BUILD":
        raise ValueError("Cancelled. No host changes were made.")
    subprocess.run(["sudo", "-v"], check=True)
    identity = subprocess.run(
        ["sudo", "-n", "id", "-u"], check=True, capture_output=True, text=True,
    )
    if identity.stdout.strip() != "0":
        raise ValueError("This sudo does not grant administrator access. No packages were installed.")
    commands = (
        [sys.executable, str(ROOT / "scripts/check-project.py")],
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "--yes", "python3", "gnupg", "git", "software-properties-common"],
        ["sudo", "apt-add-repository", "--yes", "universe"],
        ["sudo", "apt-add-repository", "--yes", PPA],
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "--yes", "--no-install-recommends", "cubic"],
        [sys.executable, str(ROOT / "scripts/fetch-base.py")],
    )
    for command in commands:
        subprocess.run(command, check=True)
    print("The verified official base is ready in build/base/. It is not a custom OS image.")
    print("In Cubic, create a separate project, import that base, and follow docs/BUILD.md.")
    print("This starter does not complete the wizard, generate a custom ISO, or verify installation.")
    subprocess.run(["cubic"], cwd=ROOT, check=True)


def interrupted_status():
    print("Local build preparation interrupted. Host packages or PPA changes already made remain; no automatic rollback was performed. Resolve any package-manager errors before retrying.", file=sys.stderr)
    return 128 + signal.SIGINT


def cli():
    try:
        main()
    except KeyboardInterrupt:
        return interrupted_status()
    except (ValueError, OSError, EOFError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.returncode in (
            128 + signal.SIGINT, -signal.SIGINT,
        ):
            return interrupted_status()
        print(f"Local build preparation stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())