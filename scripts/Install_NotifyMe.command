#!/bin/bash
cd "$(dirname "$0")"

clear
echo "=========================================="
echo "  NotifyMe Installer"
echo "=========================================="
echo ""
read -p "Press Enter to install NotifyMe to /Applications..."

rm -rf /Applications/NotifyMe.app
cp -R NotifyMe.app /Applications/
xattr -dr com.apple.quarantine /Applications/NotifyMe.app

if [ -f "entitlements.plist" ]; then
    codesign --force --deep --sign - --entitlements entitlements.plist /Applications/NotifyMe.app
else
    codesign --force --deep --sign - /Applications/NotifyMe.app
fi

echo "Adding to Login Items..."
osascript -e 'tell application "System Events" to delete login item "NotifyMe"' 2>/dev/null || true
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/NotifyMe.app", hidden:false}' 2>/dev/null || true

open /Applications/NotifyMe.app
echo ""
echo "=== Done ==="
read -p "Press Enter to close..."
