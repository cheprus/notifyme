#!/bin/bash
set -e

echo "=== 1. Building application ==="
rm -rf build dist
/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller --windowed --name NotifyMe --icon=myicon.icns app.py

echo "=== 2. Re-signing application ==="
codesign --force --deep --sign - dist/NotifyMe.app

echo "=== 3. Installing to /Applications ==="
pkill -f NotifyMe || true
rm -rf /Applications/NotifyMe.app
cp -R dist/NotifyMe.app /Applications/
xattr -dr com.apple.quarantine /Applications/NotifyMe.app
codesign --force --deep --sign - /Applications/NotifyMe.app

echo "=== 4. Building DMG for colleagues ==="
rm -rf installer
mkdir -p installer
cp -R dist/NotifyMe.app installer/
cp "Install_NotifyMe.command" installer/ 2>/dev/null || true
cp entitlements.plist installer/ 2>/dev/null || true
chmod +x "installer/Install_NotifyMe.command" 2>/dev/null || true
rm -f NotifyMe.dmg
create-dmg --volname "NotifyMe Installer" --window-size 500 300 --icon-size 100 --icon "NotifyMe.app" 130 150 --app-drop-link 370 150 "NotifyMe.dmg" "installer"

echo "=== DONE! App installed to /Applications. ==="
echo "To start use run_notifyme.command or:"
echo "/Applications/NotifyMe.app/Contents/MacOS/NotifyMe"
