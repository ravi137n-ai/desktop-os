# Building the first development image

## 1. Prepare a separate Ubuntu build host

Do not run host package-management commands in this Replit project.
Use an Ubuntu desktop computer, not a headless website server. Back up the build
host and inspect the Cubic PPA before adding it.

On that Ubuntu computer, follow Cubic's official installation instructions:

```sh
sudo apt update
sudo apt install python3 gnupg software-properties-common
sudo apt-add-repository universe
sudo apt-add-repository ppa:cubic-wizard/release
sudo apt update
sudo apt install --no-install-recommends cubic
```

The PPA is a third-party build-tool dependency. This recipe does not add it to
the finished image. Record the Cubic version used in the build notes.

Copy `os/ubuntu-desktop/` to the build host, preserving its directory structure.
Run the source checks and tests, then verify the pinned base:

```sh
python3 scripts/check-project.py
python3 -m unittest discover -s tests -v
python3 scripts/fetch-base.py --metadata-only
python3 scripts/fetch-base.py
```

Only the second fetch command downloads the multi-GB image. The signing key is
public, isolated in a temporary GnuPG home, and checked against the fingerprint
documented in Ubuntu's verification guide. The script never requests a private
key or modifies your normal GnuPG keyring.

If the pinned release disappears, the checksum differs, or the signing key
changes, stop. Update `project.json` only after checking official signed
metadata and repeating the build tests. Do not skip verification.

## 2. Import the source ISO in Cubic

1. Launch Cubic from the Ubuntu desktop.
2. Choose a dedicated build project directory, separate from this source tree.
3. Select the verified ISO from `build/base/`.
4. Use the working project name/version from `project.json` for the output
   description. Do not imply official Canonical endorsement.
5. Extract the source image through the wizard.
6. Keep existing snap seeds, especially the Ubuntu installer and Firefox.

Do not remove `snapd`: current Ubuntu installers use snap components.

## 3. Apply this project's customization

On Cubic's **Terminal** page you are root inside the extracted filesystem,
not an installed/running operating system.

```sh
mkdir -p /tmp
cd /tmp
```

Use Cubic's copy button or drag-and-drop to copy the complete `ubuntu-desktop`
source directory into `/tmp`, then:

```sh
cd /tmp/ubuntu-desktop
bash scripts/apply-in-cubic.sh --apply-in-cubic
```

The script refuses normal hosts, wrong Ubuntu series, and non-amd64 targets.
It adds packages, copies the overlay, validates GNOME defaults against the
target's real schemas, and records the installed package versions.
Package or schema errors are fatal: fix them before continuing.

Inspect these target files:

```sh
cat /usr/share/desktop-os/build.json
head /usr/share/desktop-os/packages.tsv
test -f /usr/share/doc/desktop-os/welcome.html
```

After saving any needed package inventory to the build host, remove only the
copied source folder from the virtual target before generating the image:

```sh
cd /
rm -rf -- /tmp/ubuntu-desktop
```

Do not copy your personal home directory, SSH keys, browser profiles, or
workspace secrets into the image.

## 4. Generate the image through Cubic

- Continue to Cubic's package selection and kernel/boot options.
- Keep Ubuntu's stock kernel and boot entries for this first recipe.
- Review that essential installed-system packages and everyday apps are kept.
- Let Cubic regenerate manifests, image sizes, compressed filesystems, and the
  final image checksums. Do not hand-edit the modern layered squashfs layout.
- Generate a development ISO and record the filename, checksum, Cubic version,
  source ISO checksum, and exported package inventory.

Some newer Ubuntu installer overlays can hide a custom wallpaper or settings
in the live session, even if they appear after installation. Inspect both
live and installed systems. Cubic's quick preview alone is not an install test.

## 5. Boot and install safely

Use a disposable VM with an empty virtual disk first. Never direct the
installer at a real disk containing important files.

Recommended initial VM configuration: x86-64, UEFI firmware, 4–8 GB RAM,
2+ CPU cores, 40+ GB empty virtual disk. Adjust based on measured results.

Test:

1. Live UEFI boot, desktop, installer availability.
2. Full installation to the disposable virtual disk.
3. Eject the ISO and reboot the installed system.
4. Firefox, Files, LibreOffice, VLC, Settings, and the guide launcher.
5. Internet/network settings, display resizing, and audio where VM-supported.
6. Ubuntu package updates and application updates after installation.
7. At least one supported physical PC: Wi-Fi, graphics, sound, and input.

Test offline installation, encryption, Secure Boot, and suspend/resume
separately before claiming support. Describe untested features as untested.

## 6. Record evidence and stage a candidate

Copy `config/test-report.template.json` to a build-specific report. Set
`tested_iso_sha256` to the generated ISO's real SHA-256. Each check needs a
passing status and specific evidence: VM/hardware configuration, observation,
and build log or screenshot references. Do not mark unrun tests as passed.

```sh
sha256sum /path/to/custom-image.iso
python3 scripts/prepare-release.py \
  --iso /path/to/custom-image.iso \
  --test-report /path/to/completed-test-report.json \
  --output dist/candidate-0.1.0-dev
```

A report for an earlier ISO cannot approve a newly modified ISO. Rebuilds need
new evidence. The staged folder is a local candidate, not a public release.

Use `RELEASE-CHECKLIST.md` before distribution. Uploading, release signing,
domain setup, and update-server creation are not performed by these tools.