#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# --- Таймер сборки ---
BUILD_START=$(date +%s)
BUILD_START_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")
echo "=== Build started at: $BUILD_START_HUMAN ==="

APP_NAME="NotifyMe"
APP_BUNDLE="dist/${APP_NAME}.app"
INSTALL_PATH="/Applications/${APP_NAME}.app"
APP_BIN="${INSTALL_PATH}/Contents/MacOS/${APP_NAME}"
LOG_FILE="/tmp/notifyme.log"
LOCK_FILE="/tmp/notifyme.lock"
PYINSTALLER="/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller"
ENTITLEMENTS="assets/entitlements.plist"
ICON="assets/myicon.icns"
CODESIGN_IDENTITY="NotifyMe Dev"

is_running() {
    pgrep -f "$APP_BIN" > /dev/null 2>&1
}

stop_app() {
    if is_running; then
        echo "=== Stopping running NotifyMe ==="
        pkill -f "$APP_BIN" || true
        for i in {1..50}; do
            if ! is_running; then break; fi
            sleep 0.1
        done
        if is_running; then
            echo "WARNING: NotifyMe still running after SIGTERM, sending SIGKILL"
            pkill -9 -f "$APP_BIN" || true
            sleep 0.3
        fi
        rm -f "$LOCK_FILE" 2>/dev/null || true
        echo "=== NotifyMe stopped ==="
    else
        echo "=== NotifyMe is not running ==="
    fi
}

start_app() {
    echo "=== Starting NotifyMe ==="
    open -a "$INSTALL_PATH"
    for i in {1..100}; do
        if is_running; then
            echo "=== NotifyMe started (PID: $(pgrep -f "$APP_BIN" | head -n1)) ==="
            return 0
        fi
        sleep 0.1
    done
    echo "ERROR: NotifyMe did not start within 10 seconds"
    echo "Last log lines:"
    tail -n 30 "$LOG_FILE" 2>/dev/null || true
    return 1
}

echo "=== 0. Checking prerequisites ==="
if [ ! -f "$ENTITLEMENTS" ]; then
    echo "ERROR: $ENTITLEMENTS not found!"
    exit 1
fi
plutil -lint "$ENTITLEMENTS"
if [ ! -f "$ICON" ]; then
    echo "WARNING: $ICON not found — приложение будет без иконки"
fi
if [ ! -x "$PYINSTALLER" ]; then
    echo "ERROR: pyinstaller not found at $PYINSTALLER"
    exit 1
fi

if ! security find-identity -p codesigning | grep -q "\"$CODESIGN_IDENTITY\""; then
    echo "ERROR: Code signing identity '$CODESIGN_IDENTITY' not found."
    echo "Available identities:"
    security find-identity -p codesigning
    exit 1
fi
echo "=== Using code signing identity: $CODESIGN_IDENTITY ==="

WAS_RUNNING=0
if is_running; then
    WAS_RUNNING=1
    echo "=== NotifyMe is currently running — will restart after build ==="
fi

STEP_START=$(date +%s)
echo "=== 1. Building application (pyinstaller) ==="
rm -rf build dist
"$PYINSTALLER" \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --icon="$ICON" \
  --paths src \
  --hidden-import status_bar \
  --hidden-import menu_item_view \
  --hidden-import dialogs \
  --hidden-import calendar_service \
  --hidden-import calendar_icon \
  --hidden-import state_manager \
  --hidden-import config \
  --hidden-import ui_utils \
  --hidden-import add_event_window \
  --hidden-import audio_output \
  --hidden-import event_card \
  --add-data "src/audio_output.py:." \
  --osx-bundle-identifier "com.chep.notifyme" \
  src/app.py

if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: Build failed — $APP_BUNDLE not created"
    exit 1
fi
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 1a. Build OK (${STEP_ELAPSED}s) ==="

if ! find "$APP_BUNDLE" -name "audio_output*" | grep -q .; then
    echo "ERROR: audio_output.py not found in bundle!"
    exit 1
fi
echo "=== 1b. audio_output present in bundle ==="

STEP_START=$(date +%s)
echo "=== 2. Patching Info.plist ==="
PLIST="${APP_BUNDLE}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :NSCalendarsUsageDescription string 'NotifyMe needs access to your Calendar to show upcoming meetings.'" "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSCalendarsUsageDescription 'NotifyMe needs access to your Calendar to show upcoming meetings.'" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSCalendarsFullAccessUsageDescription string 'NotifyMe needs full access to your Calendar to read events and create new ones.'" "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSCalendarsFullAccessUsageDescription 'NotifyMe needs full access to your Calendar to read events and create new ones.'" "$PLIST"
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 2a. Info.plist OK (${STEP_ELAPSED}s) ==="

STEP_START=$(date +%s)
echo "=== 3. Signing dist ==="
codesign --force --deep --sign "$CODESIGN_IDENTITY" --entitlements "$ENTITLEMENTS" "$APP_BUNDLE"
codesign -d --entitlements :- "$APP_BUNDLE" 2>&1 | grep -A 2 calendars || echo "WARNING: entitlements not found in dist!"
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 3a. Sign OK (${STEP_ELAPSED}s) ==="

STEP_START=$(date +%s)
echo "=== 4. Installing to /Applications ==="
stop_app
rm -rf "$INSTALL_PATH"
cp -R "$APP_BUNDLE" "$INSTALL_PATH"
xattr -dr com.apple.quarantine "$INSTALL_PATH" 2>/dev/null || true
codesign --force --deep --sign "$CODESIGN_IDENTITY" --entitlements "$ENTITLEMENTS" "$INSTALL_PATH"
codesign -d --entitlements :- "$INSTALL_PATH" 2>&1 | grep -A 2 calendars || echo "WARNING: entitlements not found in /Applications!"
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 4a. Install OK (${STEP_ELAPSED}s) ==="

STEP_START=$(date +%s)
echo "=== 5. Starting app ==="
start_app || exit 1
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 5a. Start OK (${STEP_ELAPSED}s) ==="

STEP_START=$(date +%s)
echo "=== 6. Building DMG ==="
rm -rf installer
mkdir -p installer
cp -R "$APP_BUNDLE" installer/
cp scripts/Install_NotifyMe.command installer/ 2>/dev/null || true
cp "$ENTITLEMENTS" installer/entitlements.plist 2>/dev/null || true
chmod +x "installer/Install_NotifyMe.command" 2>/dev/null || true
rm -f "${APP_NAME}.dmg"
create-dmg \
  --volname "${APP_NAME} Installer" \
  --window-size 500 300 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 130 150 \
  --app-drop-link 370 150 \
  "${APP_NAME}.dmg" "installer" 2>/dev/null || true
STEP_ELAPSED=$(($(date +%s) - STEP_START))
echo "=== 6a. DMG OK (${STEP_ELAPSED}s) ==="

BUILD_END=$(date +%s)
BUILD_END_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")
BUILD_TOTAL=$((BUILD_END - BUILD_START))
BUILD_MIN=$((BUILD_TOTAL / 60))
BUILD_SEC=$((BUILD_TOTAL % 60))

echo ""
echo "============================================================"
echo "  BUILD COMPLETE"
echo "  Started: $BUILD_START_HUMAN"
echo "  Ended:   $BUILD_END_HUMAN"
echo "  Duration: ${BUILD_MIN}m ${BUILD_SEC}s (total ${BUILD_TOTAL}s)"
echo "============================================================"
echo "Log: $LOG_FILE"
tail -n 5 "$LOG_FILE" 2>/dev/null || true
