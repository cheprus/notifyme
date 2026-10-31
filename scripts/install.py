#!/usr/bin/env python3
"""Install NotifyMe.app to /Applications and sign it.

Fixes:
1. Python.framework symlinks (bundle format is ambiguous).
2. base_library.zip moved to Resources + symlink.
3. audio_output.py moved to Resources + symlink.
4. sounds/ moved to Resources + symlink (codesign can't sign .mp3).
5. python3.13 renamed to python313 everywhere + symlink (codesign rejects dots).
"""
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_BUNDLE = ROOT / "dist" / "NotifyMe.app"
INSTALL_PATH = Path("/Applications/NotifyMe.app")
APP_BIN = INSTALL_PATH / "Contents" / "MacOS" / "NotifyMe"
ENTITLEMENTS = ROOT / "assets" / "entitlements.plist"
CODESIGN_IDENTITY = "NotifyMe Dev"
LOCK_FILE = Path("/tmp/notifyme.lock")


def is_running():
    return subprocess.run(
        ["pgrep", "-f", str(APP_BIN)],
        capture_output=True
    ).returncode == 0


def stop_app():
    if not is_running():
        return
    print("Stopping running NotifyMe...")
    subprocess.run(["pkill", "-f", str(APP_BIN)], check=False)
    for _ in range(50):
        if not is_running():
            break
        time.sleep(0.1)
    if is_running():
        subprocess.run(["pkill", "-9", "-f", str(APP_BIN)], check=False)
        time.sleep(0.3)
    LOCK_FILE.unlink(missing_ok=True)


def start_app():
    print("Starting NotifyMe...")
    subprocess.run(["open", "-a", str(INSTALL_PATH)], check=True)
    for _ in range(100):
        if is_running():
            return
        time.sleep(0.1)
    print("ERROR: NotifyMe did not start")
    sys.exit(1)


def fix_python_framework_symlinks(app_bundle):
    frameworks_dir = os.path.join(app_bundle, "Contents", "Frameworks")
    pattern = os.path.join(frameworks_dir, "Python.framework")
    matches = glob.glob(pattern)
    if not matches:
        print("  No Python.framework found — skip")
        return
    for fw in matches:
        print(f"  Processing: {fw}")
        versions_dir = os.path.join(fw, "Versions")
        if not os.path.isdir(versions_dir):
            continue
        versions = [
            d for d in os.listdir(versions_dir)
            if d != "Current" and os.path.isdir(os.path.join(versions_dir, d))
        ]
        if not versions:
            continue
        version = sorted(versions)[-1]
        print(f"    version: {version}")

        current_link = os.path.join(versions_dir, "Current")
        if not os.path.islink(current_link):
            if os.path.exists(current_link):
                if os.path.isdir(current_link):
                    shutil.rmtree(current_link)
                else:
                    os.remove(current_link)
            os.symlink(version, current_link)
            print(f"    Created: Versions/Current -> {version}")

        python_link = os.path.join(fw, "Python")
        if not os.path.islink(python_link):
            if os.path.exists(python_link):
                if os.path.isdir(python_link):
                    shutil.rmtree(python_link)
                else:
                    os.remove(python_link)
            os.symlink(os.path.join("Versions", "Current", "Python"), python_link)
            print("    Created: Python -> Versions/Current/Python")

        resources_link = os.path.join(fw, "Resources")
        if not os.path.islink(resources_link):
            if os.path.exists(resources_link):
                if os.path.isdir(resources_link):
                    shutil.rmtree(resources_link)
                else:
                    os.remove(resources_link)
            os.symlink(os.path.join("Versions", "Current", "Resources"), resources_link)
            print("    Created: Resources -> Versions/Current/Resources")


def _move_to_resources_and_link(app_path, filename):
    fw_dir = app_path / "Contents" / "Frameworks"
    resources_dir = app_path / "Contents" / "Resources"
    src = fw_dir / filename

    if not src.exists():
        print(f"  {filename} not found in Frameworks — skip")
        return
    if src.is_symlink():
        print(f"  {filename} already a symlink — skip")
        return

    resources_dir.mkdir(parents=True, exist_ok=True)
    target = resources_dir / filename

    print(f"  Moving {filename} to Resources...")
    shutil.move(str(src), str(target))
    os.symlink(os.path.join("..", "Resources", filename), src)
    print(f"  Created: Frameworks/{filename} -> ../Resources/{filename}")


def fix_base_library_zip(app_path):
    _move_to_resources_and_link(app_path, "base_library.zip")


def fix_audio_output_py(app_path):
    _move_to_resources_and_link(app_path, "audio_output.py")


def fix_sounds_dir(app_path):
    fw_sounds = app_path / "Contents" / "Frameworks" / "sounds"
    res_sounds = app_path / "Contents" / "Resources" / "sounds"

    if not fw_sounds.exists():
        print("  sounds/ not found in Frameworks — skip")
        return
    if fw_sounds.is_symlink():
        print("  sounds/ already a symlink — skip")
        return

    res_sounds.parent.mkdir(parents=True, exist_ok=True)
    n = len(list(fw_sounds.iterdir()))
    print(f"  Moving sounds/ to Resources ({n} files)...")
    shutil.move(str(fw_sounds), str(res_sounds))
    os.symlink(os.path.join("..", "Resources", "sounds"), fw_sounds)
    print("  Created: Frameworks/sounds -> ../Resources/sounds")


def _rename_dotted_dir(old_dir):
    if not old_dir.exists():
        return False
    if old_dir.is_symlink():
        print(f"  {old_dir} already a symlink — skip")
        return True

    new_dir = old_dir.parent / "python313"

    if new_dir.exists() and new_dir.is_dir() and not new_dir.is_symlink():
        print(f"  {new_dir} exists, removing {old_dir}")
        shutil.rmtree(old_dir)
        os.symlink("python313", old_dir)
        print(f"  Created: {old_dir.name} -> python313")
        return True

    print(f"  Renaming: {old_dir} -> {new_dir}")
    old_dir.rename(new_dir)
    os.symlink("python313", old_dir)
    print(f"  Created: {old_dir.name} -> python313")
    return True


def fix_python313_folder(app_path):
    candidates = []

    fw_root = app_path / "Contents" / "Frameworks" / "python3.13"
    if fw_root.exists():
        candidates.append(fw_root)

    res_root = app_path / "Contents" / "Resources" / "python3.13"
    if res_root.exists():
        candidates.append(res_root)

    fw = app_path / "Contents" / "Frameworks" / "Python.framework"
    if fw.exists():
        versions_dir = fw / "Versions"
        if versions_dir.exists():
            for v in versions_dir.iterdir():
                if v.is_dir() and v.name != "Current":
                    lib = v / "lib" / "python3.13"
                    if lib.exists():
                        candidates.append(lib)

    if not candidates:
        print("  No python3.13 folders found — skip")
        return

    for old_dir in candidates:
        _rename_dotted_dir(old_dir)


def sign_inner_binaries(app_path):
    fw = app_path / "Contents" / "Frameworks" / "Python.framework"
    if not fw.exists():
        print("  No Python.framework — skip inner sign")
        return

    versions_dir = fw / "Versions"
    if versions_dir.exists():
        for v in versions_dir.iterdir():
            if v.is_dir() and v.name != "Current":
                py_bin = v / "Python"
                if py_bin.exists():
                    print(f"  Signing: {py_bin}")
                    r = subprocess.run(
                        ["codesign", "--force", "--sign", CODESIGN_IDENTITY, str(py_bin)],
                        capture_output=True, text=True,
                    )
                    if r.returncode != 0:
                        print(f"    WARNING: {r.stderr.strip()}")

    count = 0
    for root, dirs, files in os.walk(fw):
        for f in files:
            if f.endswith((".so", ".dylib")):
                p = Path(root) / f
                r = subprocess.run(
                    ["codesign", "--force", "--sign", CODESIGN_IDENTITY, str(p)],
                    capture_output=True, text=True,
                )
                if r.returncode == 0:
                    count += 1
                else:
                    print(f"    WARNING: sign {p}: {r.stderr.strip()}")
    print(f"  Signed {count} .so/.dylib inside Python.framework")


def main():
    if not APP_BUNDLE.exists():
        print(f"ERROR: {APP_BUNDLE} not found — run `make build` first")
        sys.exit(1)

    result = subprocess.run(
        ["security", "find-identity", "-p", "codesigning"],
        capture_output=True, text=True,
    )
    if CODESIGN_IDENTITY not in result.stdout:
        print(f"ERROR: signing identity '{CODESIGN_IDENTITY}' not found")
        print(result.stdout)
        sys.exit(1)
    print(f"=== Using code signing identity: {CODESIGN_IDENTITY} ===")

    stop_app()

    print(f"Installing to {INSTALL_PATH}...")
    if INSTALL_PATH.exists():
        shutil.rmtree(INSTALL_PATH)
    shutil.copytree(APP_BUNDLE, INSTALL_PATH)

    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(INSTALL_PATH)], check=False)

    print("=== Fixing Python.framework symlinks ===")
    fix_python_framework_symlinks(str(INSTALL_PATH))

    print("=== Fixing python3.13 folders ===")
    fix_python313_folder(INSTALL_PATH)

    print("=== Fixing base_library.zip ===")
    fix_base_library_zip(INSTALL_PATH)

    print("=== Fixing audio_output.py ===")
    fix_audio_output_py(INSTALL_PATH)

    print("=== Fixing sounds/ ===")
    fix_sounds_dir(INSTALL_PATH)

    print("=== Signing inner binaries ===")
    sign_inner_binaries(INSTALL_PATH)

    print("=== Signing app bundle (without --deep) ===")
    r = subprocess.run(
        [
            "codesign", "--force", "--sign", CODESIGN_IDENTITY,
            "--entitlements", str(ENTITLEMENTS), str(INSTALL_PATH),
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"ERROR: codesign app failed (rc={r.returncode})")
        print("stdout:", r.stdout)
        print("stderr:", r.stderr)
        sys.exit(1)

    check = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(INSTALL_PATH)],
        capture_output=True, text=True,
    )
    combined = (check.stdout or "") + (check.stderr or "")
    if "personal-information.calendars.full" not in combined:
        print("ERROR: full calendar entitlement missing in signed bundle")
        print(combined)
        sys.exit(1)
    print("✅ Entitlements OK (full calendar access present)")

    start_app()
    print(f"✅ Installed and started: {INSTALL_PATH}")


if __name__ == "__main__":
    main()
