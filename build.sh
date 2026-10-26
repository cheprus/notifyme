#!/bin/bash
set -e

echo "=== 1. Building application ==="
rm -rf build dist
/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller --windowed --name NotifyMe --icon=myicon.icns app.py

echo "=== 2. Re-signing application ==="
codesign --force --deep --sign - dist/NotifyMe.app

echo "=== 3. Preparing installation in background ==="
# Создаем временную копию в /Applications (не трогая текущую)
TEMP_APP="/Applications/NotifyMe_new.app"
rm -rf "$TEMP_APP"
cp -R dist/NotifyMe.app "$TEMP_APP"
xattr -dr com.apple.quarantine "$TEMP_APP"
codesign --force --deep --sign - "$TEMP_APP"

echo "=== 4. Building DMG for colleagues (while old app is running) ==="
rm -rf installer
mkdir -p installer
cp -R dist/NotifyMe.app installer/
cp "Install_NotifyMe.command" installer/ 2>/dev/null || true
cp entitlements.plist installer/ 2>/dev/null || true
chmod +x "installer/Install_NotifyMe.command" 2>/dev/null || true
rm -f NotifyMe.dmg
create-dmg --volname "NotifyMe Installer" --window-size 500 300 --icon-size 100 --icon "NotifyMe.app" 130 150 --app-drop-link 370 150 "NotifyMe.dmg" "installer"

echo "=== 5. Hot-swap: replacing old app with new one ==="
# Убиваем процесс
pkill -f NotifyMe || true

# Ждём, пока процесс реально завершится (максимум 5 секунд)
echo "Waiting for old process to exit..."
for i in {1..5}; do
    if ! pgrep -f "NotifyMe" > /dev/null; then
        break
    fi
    sleep 1
done

# Удаляем старую версию и переименовываем новую
rm -rf /Applications/NotifyMe.app
mv "$TEMP_APP" /Applications/NotifyMe.app

echo "=== 6. Restarting NotifyMe ==="
# Используем ваш скрипт управления, чтобы приложение запустилось 
# в правильном контексте (через nohup, а не через open -a)
if command -v notifyme > /dev/null; then
    notifyme restart
else
    # Если notifyme не установлен, запускаем напрямую через nohup
    sleep 2
    nohup /Applications/NotifyMe.app/Contents/MacOS/NotifyMe > /tmp/notifyme.log 2>&1 &
fi

echo "=== DONE! App installed to /Applications. ==="
