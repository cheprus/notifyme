#!/usr/bin/env python3
"""Build NotifyMe.app via PyInstaller."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
PYINSTALLER = "/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller"
APP_NAME = "NotifyMe"
APP_BUNDLE = ROOT / "dist" / f"{APP_NAME}.app"
ICON = ROOT / "assets" / "myicon.icns"
SOUNDS_DIR = ROOT / "assets" / "sounds"
ENTITLEMENTS = ROOT / "assets" / "entitlements.plist"

CALENDAR_USAGE = {
    "NSCalendarsUsageDescription": (
        "NotifyMe needs access to your Calendar to show upcoming meetings."
    ),
    "NSCalendarsFullAccessUsageDescription": (
        "NotifyMe needs full access to your Calendar to read events and create new ones."
    ),
}


def run(cmd, **kwargs):
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def check_entitlements():
    if not ENTITLEMENTS.exists():
        print(f"ERROR: {ENTITLEMENTS} not found")
        sys.exit(1)

    with open(ENTITLEMENTS, "rb") as f:
        ents = plistlib.load(f)

    legacy = "com.apple.security.personal-information.calendars"
    full = "com.apple.security.personal-information.calendars.full"

    if not ents.get(full):
        print(f"ERROR: {ENTITLEMENTS} missing '{full}' (required on macOS 14+).")
        print("       Add it or the app won't be able to create events after install.")
        sys.exit(1)

    if not ents.get(legacy):
        print(f"WARNING: {ENTITLEMENTS} missing legacy '{legacy}' (macOS 13 and older).")

    print("✅ Entitlements OK (full calendar access present)")


def patch_info_plist():
    info_plist = APP_BUNDLE / "Contents" / "Info.plist"
    if not info_plist.exists():
        print(f"ERROR: {info_plist} not created by pyinstaller")
        sys.exit(1)

    with open(info_plist, "rb") as f:
        info = plistlib.load(f)

    added = []
    for key, value in CALENDAR_USAGE.items():
        if info.get(key) != value:
            info[key] = value
            added.append(key)

    with open(info_plist, "wb") as f:
        plistlib.dump(info, f)

    if added:
        print(f"✅ Info.plist patched: {', '.join(added)}")
    else:
        print("✅ Info.plist already up to date")


def main():
    if not ICON.exists():
        print(f"WARNING: {ICON} not found — app will have no icon")
    if not Path(PYINSTALLER).exists():
        print(f"ERROR: pyinstaller not found at {PYINSTALLER}")
        sys.exit(1)

    check_entitlements()

    args = [
        PYINSTALLER,
        "--noconfirm",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(ICON),
        "--paths", str(ROOT / "src"),
        "--hidden-import", "status_bar",
        "--hidden-import", "menu_item_view",
        "--hidden-import", "dialogs",
        "--hidden-import", "alarm_utils",
        "--hidden-import", "calendar_service",
        "--hidden-import", "calendar_icon",
        "--hidden-import", "state_manager",
        "--hidden-import", "config",
        "--hidden-import", "ui_utils",
        "--hidden-import", "add_event_window",
        "--hidden-import", "audio_output",
        "--hidden-import", "event_card",
        "--hidden-import", "hotkeys",
        "--hidden-import", "AVFoundation",
        "--add-data", f"{ROOT / 'src' / 'audio_output.py'}:.",
    ]

    if SOUNDS_DIR.exists() and any(SOUNDS_DIR.iterdir()):
        print(f"=== Bundling sounds from {SOUNDS_DIR} ===")
        for f in sorted(SOUNDS_DIR.iterdir()):
            print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
        args.extend(["--add-data", f"{SOUNDS_DIR}:sounds"])
    else:
        print(f"WARNING: {SOUNDS_DIR} not found or empty — no custom sounds")

    args.extend([
        "--osx-bundle-identifier", "com.chep.notifyme",
        str(ROOT / "src" / "app.py"),
    ])

    run(args)

    if not APP_BUNDLE.exists():
        print(f"ERROR: {APP_BUNDLE} not created")
        sys.exit(1)

    if not list(APP_BUNDLE.rglob("audio_output*")):
        print("ERROR: audio_output.py not found in bundle")
        sys.exit(1)

    patch_info_plist()

    sounds_in_bundle = (
        list(APP_BUNDLE.rglob("sounds/*.mp3"))
        + list(APP_BUNDLE.rglob("sounds/*.wav"))
    )
    print(f"=== Sounds in bundle: {len(sounds_in_bundle)} ===")
    for s in sounds_in_bundle[:10]:
        print(f"  {s.relative_to(APP_BUNDLE)}")

    print(f"✅ Build OK: {APP_BUNDLE}")


if __name__ == "__main__":
    main()
