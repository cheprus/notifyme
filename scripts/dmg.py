#!/usr/bin/env python3
"""Build DMG for distribution."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_BUNDLE = ROOT / "dist" / "NotifyMe.app"
APP_NAME = "NotifyMe"
INSTALLER_DIR = ROOT / "installer"
DMG_PATH = ROOT / f"{APP_NAME}.dmg"
INSTALL_COMMAND = ROOT / "scripts" / "Install_NotifyMe.command"
ENTITLEMENTS = ROOT / "assets" / "entitlements.plist"


def main():
    if not APP_BUNDLE.exists():
        print(f"ERROR: {APP_BUNDLE} not found — run `make build` first")
        return

    if INSTALLER_DIR.exists():
        shutil.rmtree(INSTALLER_DIR)
    INSTALLER_DIR.mkdir()

    shutil.copytree(APP_BUNDLE, INSTALLER_DIR / APP_BUNDLE.name)
    if INSTALL_COMMAND.exists():
        shutil.copy2(INSTALL_COMMAND, INSTALLER_DIR / INSTALL_COMMAND.name)
        (INSTALLER_DIR / INSTALL_COMMAND.name).chmod(0o755)
    if ENTITLEMENTS.exists():
        shutil.copy2(ENTITLEMENTS, INSTALLER_DIR / "entitlements.plist")

    DMG_PATH.unlink(missing_ok=True)

    try:
        subprocess.run([
            "create-dmg",
            "--volname", f"{APP_NAME} Installer",
            "--window-size", "500", "300",
            "--icon-size", "100",
            "--icon", f"{APP_NAME}.app", "130", "150",
            "--app-drop-link", "370", "150",
            str(DMG_PATH), str(INSTALLER_DIR),
        ], check=True)
        print(f"✅ DMG: {DMG_PATH}")
    except FileNotFoundError:
        print("WARNING: create-dmg not installed. DMG skipped.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: create-dmg failed: {e}")


if __name__ == "__main__":
    main()
