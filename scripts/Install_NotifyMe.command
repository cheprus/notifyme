#!/bin/bash
cd "$(dirname "$0")"

clear
echo "=========================================="
echo "  NotifyMe Installer"
echo "=========================================="
echo ""
echo "This script will install NotifyMe to your Applications folder"
echo "and add it to your Login Items (auto-start)."
echo ""
read -p "Press Enter to continue..."

echo ""
echo "1. Copying application..."
rm -rf /Applications/NotifyMe.app
cp -R NotifyMe.app /Applications/
xattr -dr com.apple.quarantine /Applications/NotifyMe.app

echo "2. Re-signing application..."
if [ -f "entitlements.plist" ]; then
    codesign --force --deep --sign - --entitlements entitlements.plist /Applications/NotifyMe.app
else
    codesign --force --deep --sign - /Applications/NotifyMe.app
fi

echo "3. Adding to Login Items..."
osascript -e 'tell application "System Events" to delete login item "NotifyMe"' 2>/dev/null
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/NotifyMe.app", hidden:false}'

echo "4. Launching application..."
open /Applications/NotifyMe.app

echo ""
echo "=== Done! NotifyMe is installed and running. ==="
echo ""
echo "If macOS blocks this file, go to:"
echo "System Settings -> Privacy & Security -> 'Open Anyway'"
echo ""
read -p "Press Enter to close..."
