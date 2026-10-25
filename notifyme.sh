#!/bin/bash

# Путь к приложению (в /Applications)
APP_PATH="/Applications/NotifyMe.app/Contents/MacOS/NotifyMe"

# Проверка, запущен ли процесс
is_running() {
    pgrep -f "$APP_PATH" > /dev/null
}

# Запуск
start_app() {
    if is_running; then
        echo "NotifyMe уже запущен."
        return
    fi
    if [ ! -f "$APP_PATH" ]; then
        echo "Ошибка: приложение не найдено в /Applications"
        return 1
    fi
    nohup "$APP_PATH" > /tmp/notifyme.log 2>&1 &
    echo "NotifyMe запущен (PID: $!)"
}

# Остановка
stop_app() {
    if ! is_running; then
        echo "NotifyMe не запущен."
        return
    fi
    pkill -f "$APP_PATH"
    echo "NotifyMe остановлен."
}

# Перезапуск
restart_app() {
    echo "Перезапуск..."
    stop_app
    sleep 1
    start_app
}

# Обработка аргументов
case "$1" in
    start|"")
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    *)
        echo "Использование: notifyme [start|stop|restart]"
        exit 1
        ;;
esac
