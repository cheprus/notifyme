#!/usr/bin/env python3
"""Build NotifyMe.app via PyInstaller."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
PYINSTALLER = "/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller"
APP_NAME = "NotifyMe"
APP_BUNDLE = ROOT / "dist" / f"{APP_NAME}.app"
ICON = ROOT / "assets" / "myicon.icns"


def run(cmd, **kwargs):
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def main():
    if not ICON.exists():
        print(f"WARNING: {ICON} not found — app will have no icon")
    if not Path(PYINSTALLER).exists():
        print(f"ERROR: pyinstaller not found at {PYINSTALLER}")
        sys.exit(1)

    run([
        PYINSTALLER,
        "--noconfirm",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(ICON),
        "--paths", str(ROOT / "src"),
        "--hidden-import", "status_bar",
        "--hidden-import", "menu_item_view",
        "--hidden-import", "dialogs",
        "--hidden-import", "calendar_service",
        "--hidden-import", "calendar_icon",
        "--hidden-import", "state_manager",
        "--hidden-import", "config",
        "--hidden-import", "ui_utils",
        "--hidden-import", "add_event_window",
        "--hidden-import", "audio_output",
        "--hidden-import", "event_card",
        "--hidden-import", "hotkeys",
        "--add-data", f"{ROOT / 'src' / 'audio_output.py'}:.",
        "--osx-bundle-identifier", "com.chep.notifyme",
        str(ROOT / "src" / "app.py"),
    ])

    if not APP_BUNDLE.exists():
        print(f"ERROR: {APP_BUNDLE} not created")
        sys.exit(1)

    if not list(APP_BUNDLE.rglob("audio_output*")):
        print("ERROR: audio_output.py not found in bundle")
        sys.exit(1)

    print(f"✅ Build OK: {APP_BUNDLE}")


if __name__ == "__main__":
    main()
