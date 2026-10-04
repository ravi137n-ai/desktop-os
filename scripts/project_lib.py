"""Shared, standard-library-only validation for the OS source setup."""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_FINGERPRINT = "843938DF228D22F7B3742BC0D94AA3F0EFE21092"
REQUIRED_CHECKS = (
    "uefi_live_boot", "vm_installation", "installed_reboot", "everyday_apps",
    "networking", "audio_and_display", "security_updates",
    "no_embedded_credentials", "licenses_and_notices", "physical_hardware",
)


def load_config(root: Path = ROOT) -> dict:
    config = json.loads((root / "project.json").read_text())
    base = config["base"]
    if base["series"] != "24.04" or base["codename"] != "noble" or base["architecture"] != "amd64":
        raise ValueError("Only Ubuntu 24.04 (noble), amd64 is supported by this recipe.")
    if base["release_url"] != "https://releases.ubuntu.com/24.04/":
        raise ValueError("The base image must come from the configured official Ubuntu release site.")
    if not re.fullmatch(r"ubuntu-24\.04(?:\.\d+)*-desktop-amd64\.iso", base["filename"]):
        raise ValueError("Invalid Ubuntu desktop ISO filename.")
    if not re.fullmatch(r"[a-f0-9]{64}", base["sha256"]):
        raise ValueError("Invalid pinned base SHA-256.")
    if base["signing_key_fingerprint"] != KEY_FINGERPRINT:
        raise ValueError("Unexpected Ubuntu image-signing key. Review any key rotation manually.")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", config["slug"]):
        raise ValueError("Invalid project slug.")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?", config["version"]):
        raise ValueError("Invalid project version.")
    if not isinstance(config["name"], str) or not config["name"].strip():
        raise ValueError("Project name is required.")
    return config


def read_packages(path: Path) -> list[str]:
    packages = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", line):
            raise ValueError(f"Invalid package name: {line!r}")
        if line in packages:
            raise ValueError(f"Duplicate package: {line}")
        packages.append(line)
    if not packages:
        raise ValueError("The package list is empty.")
    return packages


def parse_checksums(text: str) -> dict[str, str]:
    sums = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]([A-Za-z0-9._-]+)", line)
        if not match:
            raise ValueError("Invalid or unsafe checksum entry.")
        digest, filename = match.groups()
        if filename in sums:
            raise ValueError("Duplicate filename in checksum list.")
        sums[filename] = digest.lower()
    return sums


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rename_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish a file or directory without replacing any destination.

    Ubuntu supports renameat2(RENAME_NOREPLACE). Fail closed on platforms or
    filesystems without it; a check followed by ordinary rename is not safe.
    """
    rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOTSUP, "Atomic no-replace rename is unavailable.")
    rename.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(
            error, "Atomic no-replace rename failed: " + os.strerror(error),
            str(destination),
        )


def validate_signature_status(status: str) -> None:
    valid = False
    for line in status.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[:2] == ["[GNUPG:]", "VALIDSIG"] and parts[2] == KEY_FINGERPRINT:
            valid = True
        if len(parts) >= 2 and parts[1] in {"BADSIG", "REVKEYSIG", "EXPKEYSIG", "EXPSIG"}:
            raise ValueError("Invalid, revoked, or expired signature.")
    if not valid:
        raise ValueError("Checksum signature is not from the pinned Ubuntu signing key.")


def validate_report(report: dict, image_hash: str) -> None:
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("tested_iso_sha256") != image_hash:
        raise ValueError("Test report must identify this exact ISO by SHA-256.")
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError("Test checks must be an object.")
    for name in REQUIRED_CHECKS:
        check = checks.get(name, {})
        if not isinstance(check, dict) or check.get("status") != "pass" or not isinstance(check.get("evidence"), str) or not check["evidence"].strip():
            raise ValueError(f"Release is blocked: {name} needs a passing result and evidence.")