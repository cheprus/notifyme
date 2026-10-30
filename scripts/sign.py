#!/usr/bin/env python3
"""Sign NotifyMe.app with stable certificate.

PyInstaller copies Python.framework without canonical symlinks
(Versions/Current, Python, Resources). codesign then reports
"bundle format is ambiguous". We restore the symlinks before signing.
"""
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_BUNDLE = ROOT / "dist" / "NotifyMe.app"
ENTITLEMENTS = ROOT / "assets" / "entitlements.plist"
CODESIGN_IDENTITY = "NotifyMe Dev"


def run(cmd, check=True):
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def fix_python_framework_symlinks(app_bundle):
    """Restore canonical symlinks in Python.framework."""
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
            print("    No Versions/ — skip")
            continue

        versions = [
            d for d in os.listdir(versions_dir)
            if d != "Current" and os.path.isdir(os.path.join(versions_dir, d))
        ]
        if not versions:
            print("    No version dirs — skip")
            continue
        version = sorted(versions)[-1]
        print(f"    version: {version}")

        # 1. Versions/Current -> version
        current_link = os.path.join(versions_dir, "Current")
        if os.path.islink(current_link):
            print("    Versions/Current already a symlink")
        else:
            if os.path.exists(current_link):
                if os.path.isdir(current_link):
                    shutil.rmtree(current_link)
                else:
                    os.remove(current_link)
            os.symlink(version, current_link)
            print(f"    Created: Versions/Current -> {version}")

        # 2. Python -> Versions/Current/Python
        python_link = os.path.join(fw, "Python")
        if os.path.islink(python_link):
            print("    Python already a symlink")
        else:
            if os.path.exists(python_link):
                if os.path.isdir(python_link):
                    shutil.rmtree(python_link)
                else:
                    os.remove(python_link)
            os.symlink(os.path.join("Versions", "Current", "Python"), python_link)
            print("    Created: Python -> Versions/Current/Python")

        # 3. Resources -> Versions/Current/Resources
        resources_link = os.path.join(fw, "Resources")
        if os.path.islink(resources_link):
            print("    Resources already a symlink")
        else:
            if os.path.exists(resources_link):
                if os.path.isdir(resources_link):
                    shutil.rmtree(resources_link)
                else:
                    os.remove(resources_link)
            os.symlink(os.path.join("Versions", "Current", "Resources"), resources_link)
            print("    Created: Resources -> Versions/Current/Resources")

        # 4. Headers -> Versions/Current/Headers (если есть)
        headers_link = os.path.join(fw, "Headers")
        headers_target = os.path.join(versions_dir, version, "Headers")
        if os.path.isdir(headers_target) and not os.path.islink(headers_link):
            if os.path.exists(headers_link):
                if os.path.isdir(headers_link):
                    shutil.rmtree(headers_link)
                else:
                    os.remove(headers_link)
            os.symlink(os.path.join("Versions", "Current", "Headers"), headers_link)
            print("    Created: Headers -> Versions/Current/Headers")


def main():
    if not ENTITLEMENTS.exists():
        print(f"ERROR: {ENTITLEMENTS} not found")
        sys.exit(1)
    if not APP_BUNDLE.exists():
        print(f"ERROR: {APP_BUNDLE} not found — run `make build` first")
        sys.exit(1)

    # Проверка сертификата
    result = subprocess.run(
        ["security", "find-identity", "-p", "codesigning"],
        capture_output=True, text=True
    )
    if CODESIGN_IDENTITY not in result.stdout:
        print(f"ERROR: signing identity '{CODESIGN_IDENTITY}' not found")
        print("Available identities:")
        print(result.stdout)
        sys.exit(1)
    print(f"=== Using code signing identity: {CODESIGN_IDENTITY} ===")

    # Восстановить симлинки
    print("=== Fixing Python.framework symlinks ===")
    fix_python_framework_symlinks(str(APP_BUNDLE))

    # Подписать
    print("=== Signing ===")
    r = subprocess.run(
        [
            "codesign", "--force", "--deep", "--sign", CODESIGN_IDENTITY,
            "--entitlements", str(ENTITLEMENTS), str(APP_BUNDLE),
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"ERROR: codesign failed (rc={r.returncode})")
        print("stdout:", r.stdout)
        print("stderr:", r.stderr)
        sys.exit(1)

    # Проверить entitlements
    check = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(APP_BUNDLE)],
        capture_output=True, text=True,
    )
    if "calendars" not in check.stdout and "calendars" not in check.stderr:
        print("WARNING: entitlements not found")
    else:
        print("✅ Entitlements OK")

    print(f"✅ Signed: {APP_BUNDLE}")


if __name__ == "__main__":
    main()
