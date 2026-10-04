#!/usr/bin/env python3
"""Stage a local candidate only after a report passes for this exact ISO."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from project_lib import ROOT, load_config, sha256, validate_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", required=True, type=Path)
    parser.add_argument("--test-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="A new directory; existing paths are never overwritten.")
    args = parser.parse_args()
    config = load_config()
    image = args.iso.resolve(strict=True)
    report = json.loads(args.test_report.read_text())
    if not image.is_file() or image.suffix.lower() != ".iso":
        raise ValueError("A regular ISO image is required.")
    with image.open("rb") as stream:
        stream.seek(16 * 2048 + 1)
        if stream.read(5) != b"CD001":
            raise ValueError("The file does not contain an ISO9660 volume descriptor.")
    digest = sha256(image)
    if digest == config["base"]["sha256"]:
        raise ValueError("This is the unmodified Ubuntu base image, not a custom OS candidate.")
    validate_report(report, digest)
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Output already exists. Choose a new directory; nothing will be overwritten.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < image.stat().st_size + 1024**3:
        raise ValueError("Insufficient space to stage a copy of the candidate image.")
    filename = f"{config['slug']}-{config['version']}-amd64.iso"
    with tempfile.TemporaryDirectory(prefix=".release-stage-", dir=output.parent) as temp:
        stage = Path(temp) / "candidate"
        stage.mkdir()
        shutil.copy2(image, stage / filename)
        if sha256(stage / filename) != digest:
            raise ValueError("Image changed while staging; checksum verification failed.")
        (stage / "SHA256SUMS").write_text(f"{digest}  {filename}\n")
        (stage / "test-report.json").write_text(json.dumps(report, indent=2) + "\n")
        (stage / "release.json").write_text(json.dumps({
            "project": config["name"], "version": config["version"],
            "status": "locally-staged-candidate-not-published",
            "filename": filename, "sha256": digest, "base": config["base"],
            "tests": "operator-supplied evidence; this script does not boot or install the OS",
        }, indent=2) + "\n")
        shutil.copy2(ROOT / "docs/RELEASE-CHECKLIST.md", stage / "RELEASE-CHECKLIST.md")
        shutil.copy2(ROOT / "NOTICE.md", stage / "NOTICE.md")
        stage.rename(output)
    print(f"Local release candidate staged: {output}")
    print("NOT published or digitally signed. Complete distribution/license review and sign release checksums before uploading.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"Release preparation blocked: {error}", file=sys.stderr)
        sys.exit(1)