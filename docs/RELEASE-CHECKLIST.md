# Release checklist — not completed

No ISO or release exists yet. These checks must be completed for a specific build.

## Build integrity
- [ ] Official base checksum signature verified against the pinned Ubuntu key.
- [ ] Base ISO checksum matches the pin.
- [ ] Cubic version, build date, recipe revision, and package inventory recorded.
- [ ] Generated custom ISO has its own SHA-256 and is not the stock base image.
- [ ] Test evidence refers to this exact generated ISO checksum.

## Functional tests
- [ ] UEFI live boot and installer.
- [ ] Installation in a disposable VM and reboot without the ISO.
- [ ] Everyday applications, software installation, and accessibility settings.
- [ ] Networking, audio, and display.
- [ ] Ubuntu security updates and application updates.
- [ ] Physical hardware tests; published support limited to tested models.
- [ ] Offline, Secure Boot, encryption, and suspend/resume claims match evidence.

## Security and licensing
- [ ] No API keys, tokens, passwords, private SSH/GPG keys, or personal files.
- [ ] No unexpected startup services, third-party repositories, or default accounts.
- [ ] No change to the Ubuntu package identity that breaks updates.
- [ ] Canonical trademark policy and third-party redistribution licenses reviewed.
- [ ] Required copyright notices and applicable corresponding source provided.
- [ ] A license chosen for this project's new source files.
- [ ] Release signing performed using the maintainer's trusted signing process.
      Do not put a private signing key in this repository or an OS image.

## Distribution
- [ ] Honest development/stable status and known issues.
- [ ] Download host can serve the actual ISO size and bandwidth.
- [ ] Signed checksum files and a separate trusted public-key verification method.
- [ ] USB creation instructions explain that writing an image erases the chosen USB.
- [ ] Installation guide requires backups and warns about disk erasure.
- [ ] Support contact, security-reporting process, and maintenance ownership defined.
- [ ] Download page links to the real uploaded image, not a placeholder.

Publishing a companion website is not equivalent to publishing the OS image.