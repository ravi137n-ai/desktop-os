# Ubuntu-based desktop OS source setup

**Status: source and build setup only. No custom ISO has been generated,
booted, installed, certified, or published.**

This is a separate OS source project, not part of Ra Vision or Civil Engineering
AI. “Desktop OS” is a working name, not a finalized brand.

## Initial scope

- Ubuntu 24.04 LTS (noble), official amd64 desktop image.
- Ubuntu GNOME desktop and installer; existing browser and App Center.
- LibreOffice, VLC, editor, calculator, and system monitor.
- Custom wallpaper, dock defaults, and a local getting-started guide.
- Existing Ubuntu repositories and update infrastructure remain intact.
- No bundled users, passwords, API keys, cloud accounts, or new telemetry.

The recipe pins a published 24.04 desktop point release and checksum in
`project.json`. It does not claim this is the newest Ubuntu LTS. A newer series
requires a separately tested recipe. Windows/macOS application compatibility,
ARM/Apple Silicon, and universal hardware support are not provided.

## Files

| Path | Purpose |
| --- | --- |
| `project.json` | Working identity, target architecture, pinned official base |
| `config/packages.txt` | Additional Ubuntu packages |
| `overlay/` | Desktop defaults, wallpaper, launcher, local guide |
| `scripts/check-project.py` | Non-destructive recipe validation |
| `scripts/fetch-base.py` | Signed-metadata and image checksum verification |
| `scripts/apply-in-cubic.sh` | Apply additions inside Cubic's chroot only |
| `scripts/prepare-release.py` | Stage a tested local candidate, never publish |
| `config/test-report.template.json` | Required evidence tied to an exact ISO |
| `docs/BUILD.md` | Detailed build and test instructions |
| `docs/RELEASE-CHECKLIST.md` | Release, security, and licensing checks |
| `tests/` | Source-tool tests; not OS boot tests |

## Check the source here

From this directory:

```sh
python3 scripts/check-project.py
python3 -m unittest discover -s tests -v
```

These commands do not install packages, customize your running computer,
download a multi-GB image, or write disks.

## GitHub source verification

`.github/workflows/build-os.yml` is a manually started source-verification
workflow for the standalone OS repository. It runs the source tests and checks
the official Ubuntu image's signed metadata on an Ubuntu runner.

This workflow **does not build an ISO, run Cubic, boot a VM, or install the OS**.
It is a preliminary verification step, not a completed automated image builder.
The image-build workflow still needs implementation and execution.

## Build on an Ubuntu computer

Use a separate Ubuntu desktop build computer with admin rights, internet,
roughly 40 GB free storage, and preferably 8 GB RAM or more. These are build
recommendations, not measured minimum requirements for the resulting OS.

Use Cubic's official installation instructions:
https://github.com/PJ-Singh-001/Cubic/wiki/Install-Cubic

After installing Cubic and GnuPG there:

```sh
python3 scripts/fetch-base.py --metadata-only
python3 scripts/fetch-base.py
```

The downloader verifies the checksum signature against a pinned Ubuntu signing
key before accepting the pinned base image. It refuses changed metadata,
checksum mismatches, unsafe filenames, or incomplete previous downloads.

Open Cubic, create a project outside this source folder, and import the verified
base ISO. Keep the original installer and snap seeds. In Cubic's virtual
terminal, copy this source directory into `/tmp/ubuntu-desktop`, then run:

```sh
cd /tmp/ubuntu-desktop
bash scripts/apply-in-cubic.sh --apply-in-cubic
```

**Do not run that command on your normal computer or in Replit.** It requires a
detected Ubuntu chroot and root permissions, and changes that target filesystem.
The actual ISO assembly is Cubic's interactive wizard, not an automated build
implemented by this repository. See `docs/BUILD.md` for all steps.

## Before publishing

Boot and install the actual generated ISO in a disposable VM, then test selected
hardware with explicit permission and backups. Complete the test report for
the exact ISO checksum. Only then stage a candidate:

```sh
python3 scripts/prepare-release.py \
  --iso /path/to/custom-image.iso \
  --test-report /path/to/completed-test-report.json \
  --output dist/candidate-0.1.0-dev
```

The helper checks report completeness and integrity, not the truth of manual
test evidence. It does not prove bootability, sign the release, upload it, or
publish anything. The `-dev` version remains a development candidate.

Keep Ubuntu's license notices, review branding/distribution obligations, choose
a license for the new source files, and sign the final checksum list using the
release maintainer's signing process before distributing it.

## Important limitations

- Source tools have no external Python dependencies.
- Customization uses a target-local `flock` to prevent overlapping operations.
  Leave the empty lock file in place; the lock itself is released on process exit.
- Final image and candidate publication uses Linux's atomic no-replace rename.
  Unsupported platforms/filesystems fail explicitly rather than risk overwriting.
- Cubic adds a third-party PPA on the Ubuntu **build host**, not in the OS image.
  Review that trust decision before installing it.
- Live-session installer overlays can hide customizations that appear in the
  installed system. Test both environments separately.
- Retain `snapd` and the installer snap. Snap services cannot run normally in
  Cubic's virtual terminal; do not attempt `snap install` there.
- Package updates make builds non-bit-reproducible unless an archive snapshot
  and exact dependency versions are also captured.
- Secure Boot, disk encryption, offline installation, suspend/resume, and
  proprietary drivers require explicit testing; none is claimed here.
- The current workspace's web publishing configuration remains unchanged.

## References

- Cubic: https://github.com/PJ-Singh-001/Cubic
- Cubic terminal: https://github.com/PJ-Singh-001/Cubic/wiki/Terminal-Page
- Ubuntu base: https://releases.ubuntu.com/24.04/
- Ubuntu verification: https://ubuntu.com/tutorials/how-to-verify-ubuntu
- Distribution policy: https://ubuntu.com/legal/intellectual-property-policy