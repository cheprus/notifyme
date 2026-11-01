# src/app.py
import contextlib
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from AppKit import NSApplication, NSRunningApplication
from Foundation import NSObject, NSTimer

import audio_output  # noqa: F401
from calendar_service import request_calendar_access

LOCK_FILE = Path("/tmp/notifyme.lock")
BUNDLE_ID = "com.chep.notifyme"


def _find_pids():
    """Найти PID процессов NotifyMe по args — без фильтра по comm.

    - .app bundle: args содержит 'NotifyMe.app/Contents/MacOS/NotifyMe'
    - dev-режим: args содержит 'src/app.py' (и не является 'notifyme' entry-point)
    """
    pids = []
    try:
        r = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True, text=True,
        )
        me = os.getpid()
        for line in r.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            pid_s, args = parts
            if not pid_s.isdigit():
                continue
            pid = int(pid_s)
            if pid == me:
                continue
            if "NotifyMe.app/Contents/MacOS/NotifyMe" in args:
                pids.append(pid)
            elif "src/app.py" in args:
                # dev-режим. Entry-point `notifyme` тоже может содержать
                # 'src/app.py' в args в редких случаях — отсекаем по 'bin/notifyme'.
                if "bin/notifyme" in args:
                    continue
                pids.append(pid)
    except Exception as e:
        print(f"[DEBUG] _find_pids error: {e}", flush=True)
    return sorted(set(pids))


def _refresh_menu_bar():
    """Перезапустить SystemUIServer, чтобы убрать фантомные NSStatusItem.

    Безопасно: Finder/Dock/приложения не трогаются, только правый угол меню-бара.
    """
    print("Refreshing menu bar (removing phantom icons)...")
    subprocess.run(
        ["killall", "SystemUIServer"],
        check=False, capture_output=True,
    )
    time.sleep(1.2)


def _stop():
    pids = _find_pids()
    if not pids:
        print("NotifyMe is not running.")
        LOCK_FILE.unlink(missing_ok=True)
        _refresh_menu_bar()
        return 0

    print(f"Stopping NotifyMe (pids: {', '.join(map(str, pids))})...")
    for pid in pids:
        with contextlib.suppress(Exception):
            os.kill(pid, signal.SIGTERM)

    stopped_cleanly = False
    for _ in range(100):
        if not _find_pids():
            stopped_cleanly = True
            break
        time.sleep(0.1)

    if not stopped_cleanly:
        remaining = _find_pids()
        if remaining:
            print(f"Force-killing remaining pids: {remaining}")
            for pid in remaining:
                with contextlib.suppress(Exception):
                    os.kill(pid, signal.SIGKILL)
            time.sleep(0.3)

    LOCK_FILE.unlink(missing_ok=True)
    print("NotifyMe stopped.")
    _refresh_menu_bar()
    return 0


def _start():
    app_path = Path("/Applications/NotifyMe.app")
    if not app_path.exists():
        print(f"ERROR: {app_path} not found. Run `make release` first.")
        return 1
    if _find_pids():
        print("NotifyMe is already running, activating existing instance...")
        subprocess.run(["open", "-a", str(app_path)], check=False)
        return 0
    print(f"Starting {app_path}...")
    subprocess.run(["open", "-a", str(app_path)], check=False)
    for _ in range(100):
        if _find_pids():
            print("NotifyMe started.")
            return 0
        time.sleep(0.1)
    print("ERROR: NotifyMe did not start.")
    return 1


def _restart():
    _stop()
    return _start()


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        app = NSApplication.sharedApplication()

        app.setActivationPolicy_(0)  # Regular
        with contextlib.suppress(Exception):
            app.activateIgnoringOtherApps_(True)

        self.store = request_calendar_access()
        self.status_bar = None
        self.ui_timer = None
        self.notify_timer = None

        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "switchToAccessory:", None, False
        )

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_visible):
        print("[DEBUG] applicationShouldHandleReopen", flush=True)
        if self.status_bar is not None:
            try:
                self.status_bar.update()
            except Exception:
                pass
        return True

    def switchToAccessory_(self, timer):
        print("[DEBUG] Switching to Accessory policy", flush=True)
        NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory

        from status_bar import StatusBarController
        self.status_bar = StatusBarController.alloc().initWithApp_(self)
        self.status_bar.update()

        self.ui_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self, "tickUI:", None, True
        )
        self.notify_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self.status_bar, "checkNotifications:", None, True
        )

    def tickUI_(self, timer):
        if self.status_bar is not None:
            self.status_bar.update()

    def applicationWillTerminate_(self, notification):
        with contextlib.suppress(Exception):
            from alarm_utils import close_all_alarms
            close_all_alarms()


def _already_running_via_launchservices():
    try:
        apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(BUNDLE_ID)
        my_pid = os.getpid()
        for app in apps:
            if app.processIdentifier() != my_pid and not app.isTerminated():
                return True
    except Exception:
        pass
    return False


def main():
    print(f"[DEBUG] sys.argv = {sys.argv}", flush=True)

    if "--add-event" in sys.argv:
        print("[DEBUG] --add-event mode detected", flush=True)
        from add_event_window import main as show_form
        show_form()
        sys.exit(0)

    if len(sys.argv) >= 2:
        cmd = sys.argv[1]
        if cmd == "stop":
            sys.exit(_stop())
        elif cmd == "start":
            sys.exit(_start())
        elif cmd == "restart":
            sys.exit(_restart())
        elif cmd == "refresh":
            _refresh_menu_bar()
            sys.exit(0)
        elif cmd in ("--help", "-h", "help"):
            print("Usage: notifyme [start|stop|restart|refresh|--add-event]")
            sys.exit(0)

    if _already_running_via_launchservices():
        print("NotifyMe is already running (LaunchServices), exiting.", flush=True)
        sys.exit(0)

    lock_file = open(LOCK_FILE, "w")  # noqa: SIM115
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("NotifyMe is already running (lock file).", flush=True)
        sys.exit(0)

    try:
        app = NSApplication.sharedApplication()
        delegate = AppDelegate.alloc().init()
        app.setDelegate_(delegate)
        app.run()
    finally:
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        with contextlib.suppress(Exception):
            os.remove(LOCK_FILE)


if __name__ == "__main__":
    main()
