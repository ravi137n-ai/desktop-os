#!/usr/bin/env python3
"""Download the pinned official image only after checking its signed metadata."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from project_lib import ROOT, KEY_FINGERPRINT, load_config, parse_checksums, rename_no_replace, sha256, validate_signature_status


def fetch_small(url: str, destination: Path):
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Signing metadata exceeds the size limit.")
    destination.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-only", action="store_true", help="Verify signed metadata without downloading the multi-GB ISO.")
    args = parser.parse_args()
    config = load_config()
    base = config["base"]
    if not shutil.which("gpg"):
        raise ValueError("GnuPG is required. Run this on the Ubuntu build computer after following README.md.")
    build = ROOT / "build/base"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ubuntu-signature-") as temp:
        home = Path(temp)
        os.chmod(home, 0o700)
        sums, signature, key = (home / name for name in ("SHA256SUMS", "SHA256SUMS.gpg", "signing-key.asc"))
        fetch_small(base["release_url"] + "SHA256SUMS", sums)
        fetch_small(base["release_url"] + "SHA256SUMS.gpg", signature)
        fetch_small("https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x" + KEY_FINGERPRINT, key)
        subprocess.run(["gpg", "--homedir", str(home), "--batch", "--import", str(key)], check=True, capture_output=True)
        verified = subprocess.run(
            ["gpg", "--homedir", str(home), "--batch", "--status-fd", "1", "--verify", str(signature), str(sums)],
            capture_output=True, text=True,
        )
        # Ubuntu metadata may carry a second legacy signature for a key we
        # deliberately did not import. Require the pinned RSA signature itself,
        # rather than rejecting a valid pinned signature for an unknown second key.
        validate_signature_status(verified.stdout)
        published = parse_checksums(sums.read_text())
        if published.get(base["filename"]) != base["sha256"]:
            raise ValueError("Pinned ISO or checksum differs from the signed Ubuntu release metadata. Stop and review.")
        shutil.copy2(sums, build / sums.name)
        shutil.copy2(signature, build / signature.name)
    (build / "source-verification.json").write_text(json.dumps({
        "filename": base["filename"], "sha256": base["sha256"],
        "signing_key": KEY_FINGERPRINT, "signed_metadata_verified": True,
    }, indent=2) + "\n")
    print("Pinned ISO matches the signed Ubuntu checksum metadata.")
    if args.metadata_only:
        print("No ISO downloaded.")
        return
    target = build / base["filename"]
    if target.exists():
        if sha256(target) != base["sha256"]:
            raise ValueError(f"Existing ISO failed checksum verification: {target}. Remove it manually before retrying.")
        print(f"Existing verified image: {target}")
        return
    partial = target.with_suffix(".iso.part")
    if partial.exists():
        raise ValueError(f"Incomplete download exists: {partial}. Remove it manually before retrying.")
    owns_partial = False
    try:
        with urllib.request.urlopen(base["release_url"] + base["filename"], timeout=120) as response, partial.open("xb") as output:
            owns_partial = True
            size = int(response.headers.get("Content-Length", "0"))
            if not size or size > 12 * 1024**3:
                raise ValueError("Missing or unreasonable ISO size.")
            if shutil.disk_usage(build).free < size + 1024**3:
                raise ValueError("Not enough disk space for the ISO download.")
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > size:
                    raise ValueError("ISO download exceeded its declared size.")
                output.write(chunk)
            if downloaded != size:
                raise ValueError("Incomplete ISO download.")
        if sha256(partial) != base["sha256"]:
            raise ValueError("Downloaded ISO failed checksum verification.")
        rename_no_replace(partial, target)
    except Exception:
        if owns_partial:
            partial.unlink(missing_ok=True)
        raise
    print(f"Verified image: {target}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Base image preparation failed: {error}", file=sys.stderr)
        sys.exit(1)