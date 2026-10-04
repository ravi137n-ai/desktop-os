#!/usr/bin/env bash
# Run ONLY in Cubic's virtual terminal, not on the build computer or Replit.
set -euo pipefail
PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--check" ]]; then
  exec python3 "$PROJECT/scripts/check-project.py"
fi
if [[ "${1:-}" != "--apply-in-cubic" || $# -ne 1 ]]; then
  echo "Usage: bash scripts/apply-in-cubic.sh --check | --apply-in-cubic" >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  echo "Refusing: root access inside Cubic's virtual terminal is required." >&2
  exit 1
fi
if ! command -v systemd-detect-virt >/dev/null || ! systemd-detect-virt --chroot >/dev/null; then
  echo "Refusing: a chroot was not detected. Do not run this on a normal host." >&2
  exit 1
fi
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != amd64 ]]; then
  echo "Refusing: this recipe requires an Ubuntu 24.04 amd64 root filesystem." >&2
  exit 1
fi
for tool in python3 apt-get dpkg-query glib-compile-schemas find install; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }
done
python3 "$PROJECT/scripts/check-project.py"
mapfile -t PACKAGES < <(python3 - "$PROJECT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from project_lib import read_packages
print("\n".join(read_packages(Path(sys.argv[1]) / "config/packages.txt")))
PY
)
[[ ${#PACKAGES[@]} -gt 0 ]] || { echo "Empty package list." >&2; exit 1; }

# Prevent package post-install scripts from attempting to start services.
# Preserve any existing policy and restore it even if apt fails.
POLICY=/usr/sbin/policy-rc.d
BACKUP="$(mktemp -d)"
HAD_POLICY=false
if [[ -e "$POLICY" || -L "$POLICY" ]]; then
  cp -a "$POLICY" "$BACKUP/policy-rc.d"
  HAD_POLICY=true
fi
restore_policy() {
  rm -f "$POLICY"
  if "$HAD_POLICY"; then cp -a "$BACKUP/policy-rc.d" "$POLICY"; fi
  rm -rf -- "$BACKUP"
}
trap restore_policy EXIT
rm -f "$POLICY"
printf '#!/bin/sh\nexit 101\n' > "$POLICY"
chmod 755 "$POLICY"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install --yes "${PACKAGES[@]}"

# Do not change /etc/os-release, installer snaps, signed repositories,
# the kernel, users, passwords, or the original image's boot configuration.
while IFS= read -r -d '' FILE; do
  TARGET="/${FILE#"$PROJECT/overlay/"}"
  install -D -m 0644 -o 0 -g 0 "$FILE" "$TARGET"
done < <(find "$PROJECT/overlay" -type f -print0)
glib-compile-schemas --strict --dry-run /usr/share/glib-2.0/schemas
glib-compile-schemas --strict /usr/share/glib-2.0/schemas
install -d /usr/share/desktop-os
install -m 644 "$PROJECT/project.json" /usr/share/desktop-os/build.json
dpkg-query -W -f='${Package}\t${Version}\n' > /usr/share/desktop-os/packages.tsv
apt-get clean
echo "Customization applied. Continue Cubic's wizard to generate the ISO."
echo "No live boot, installed-system, or hardware test has been performed."