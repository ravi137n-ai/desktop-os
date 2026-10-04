#!/usr/bin/env python3
"""Check the recipe without root, package installation, or host modification."""
import configparser
import subprocess
import sys
import xml.etree.ElementTree as ET

from project_lib import ROOT, load_config, read_packages


def main():
    config = load_config()
    packages = read_packages(ROOT / "config/packages.txt")
    overlay = ROOT / "overlay"
    for path in overlay.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Overlay symlinks are not allowed: {path}")
        if path.is_file() and not path.relative_to(overlay).as_posix().startswith("usr/share/"):
            raise ValueError(f"Overlay may not overwrite system identity or credentials: {path}")
    ET.parse(overlay / "usr/share/backgrounds/desktop-os-wallpaper.svg")
    ET.parse(overlay / "usr/share/gnome-background-properties/desktop-os.xml")
    launcher = configparser.ConfigParser(interpolation=None)
    launcher.read(overlay / "usr/share/applications/desktop-os-welcome.desktop")
    if launcher["Desktop Entry"]["Exec"] != "xdg-open /usr/share/doc/desktop-os/welcome.html":
        raise ValueError("Unexpected welcome launcher command.")
    overrides = configparser.ConfigParser(interpolation=None)
    overrides.read(overlay / "usr/share/glib-2.0/schemas/99_desktop-os.gschema.override")
    if set(overrides.sections()) != {"org.gnome.desktop.background", "org.gnome.shell:ubuntu"}:
        raise ValueError("Unexpected GNOME schema override.")
    subprocess.run(["bash", "-n", str(ROOT / "scripts/apply-in-cubic.sh")], check=True)
    print(f"Recipe valid: {config['name']} {config['version']}, {len(packages)} added packages.")
    print("Source validation only. No installer, OS boot, package install, or hardware test was performed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        sys.exit(1)