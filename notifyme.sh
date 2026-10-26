#!/bin/bash
APP_PATH="/Applications/NotifyMe.app/Contents/MacOS/NotifyMe"

is_running() {
    pgrep -f "$APP_PATH" > /dev/null
}

start_app() {
    if is_running; then
        echo "NotifyMe is already running."
        return
    fi
    if [ ! -f "$APP_PATH" ]; then
        echo "Error: Application not found in /Applications"
        return 1
    fi
    nohup "$APP_PATH" > /tmp/notifyme.log 2>&1 &
    echo "NotifyMe started (PID: $!)"
}

stop_app() {
    if ! is_running; then
        echo "NotifyMe is not running."
        return
    fi
    pkill -f "$APP_PATH"
    echo "NotifyMe stopped."
}

restart_app() {
    echo "Restarting..."
    stop_app
    sleep 1
    start_app
}

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
        echo "Usage: notifyme [start|stop|restart]"
        exit 1
        ;;
esac
