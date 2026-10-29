#!/bin/bash

if [ -d "/Applications/NotifyMe.app" ]; then
    APP_PATH="/Applications/NotifyMe.app/Contents/MacOS/NotifyMe"
else
    echo "Приложение не найдено в /Applications"
    exit 1
fi

# Запускаем в фоне, отвязав от терминала
nohup "$APP_PATH" > /tmp/notifyme.log 2>&1 &
echo "NotifyMe запущен в фоне (PID: $!)"
echo "Логи: /tmp/notifyme.log"
