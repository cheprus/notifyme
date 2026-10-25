#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

# Переходим в папку проекта
cd /Users/chep/dev/python/notyfyme

echo "=== 1. Очистка старых сборок ==="
rm -rf build dist NotifyMe.spec

echo "=== 2. Сборка через PyInstaller ==="
/Library/Frameworks/Python.framework/Versions/3.13/bin/pyinstaller --windowed --name NotifyMe app.py

echo "=== 3. Добавление ключа доступа к Календарю в Info.plist ==="
# Путь к Info.plist внутри собранного приложения
PLIST_PATH="dist/NotifyMe.app/Contents/Info.plist"

# Проверяем, существует ли файл
if [ -f "$PLIST_PATH" ]; then
    # Добавляем ключ NSCalendarsFullAccessUsageDescription (если его нет)
    /usr/libexec/PlistBuddy -c "Add :NSCalendarsFullAccessUsageDescription string 'NotifyMe показывает ваши встречи и напоминает о них.'" "$PLIST_PATH" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :NSCalendarsFullAccessUsageDescription 'NotifyMe показывает ваши встречи и напоминает о них.'" "$PLIST_PATH"
    echo "Ключ доступа к Календарю добавлен."
else
    echo "ОШИБКА: Info.plist не найден по пути $PLIST_PATH"
    exit 1
fi

echo "=== 4. Копирование в /Applications ==="
# Удаляем старую версию, если есть
rm -rf /Applications/NotifyMe.app

# Копируем новую
cp -R dist/NotifyMe.app /Applications/

echo "=== 5. Снятие карантина ==="
xattr -dr com.apple.quarantine /Applications/NotifyMe.app

echo "=== 6. Готово! Запускаем ==="
open /Applications/NotifyMe.app
