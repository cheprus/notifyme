# src/app.py
import contextlib
import fcntl
import os
import plistlib
import signal
import subprocess
import sys
import time
from pathlib import Path

from AppKit import (
    NSApplication,
    NSRunLoop,
    NSRunLoopCommonModes,
    NSRunningApplication,
)
from Foundation import NSObject, NSTimer

import audio_output  # noqa: F401
from calendar_service import request_calendar_access

LOCK_FILE = Path("/tmp/notifyme.lock")
BUNDLE_ID = "com.chep.notifyme"
INSTALLED_APP = Path("/Applications/NotifyMe.app")


def _find_pids():
    pids = []
    try:
        r = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True)
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
                if "bin/notifyme" in args:
                    continue
                pids.append(pid)
    except Exception as e:
        print(f"[DEBUG] _find_pids error: {e}", flush=True)
    return sorted(set(pids))


def _refresh_menu_bar():
    print("Refreshing menu bar (removing phantom icons)...")
    subprocess.run(["killall", "SystemUIServer"], check=False, capture_output=True)
    for _ in range(50):
        time.sleep(0.1)
        r = subprocess.run(["pgrep", "-x", "SystemUIServer"], capture_output=True)
        if r.returncode == 0:
            break
    time.sleep(0.5)


def _read_build_date():
    """BuildDate из Info.plist установленного .app, fallback — из version.py."""
    try:
        info_plist = INSTALLED_APP / "Contents" / "Info.plist"
        if info_plist.exists():
            with open(info_plist, "rb") as f:
                bd = plistlib.load(f).get("BuildDate")
            if bd:
                return bd, "Info.plist"
    except Exception:
        pass
    try:
        import version
        return getattr(version, "APP_DATE", "?"), "version.py (APP_DATE)"
    except Exception:
        return "?", "unknown"


def _status():
    """Показать состояние NotifyMe: процессы, SystemUIServer, версия, build."""
    print("=== NotifyMe status ===")

    pids = _find_pids()
    if pids:
        print(f"Processes: {', '.join(map(str, pids))}")
        try:
            r = subprocess.run(
                ["ps", "-p", ",".join(map(str, pids)), "-o", "pid=,etime=,comm="],
                capture_output=True, text=True,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line:
                    print(f"  {line}")
        except Exception as e:
            print(f"  (ps failed: {e})")
    else:
        print("Processes: none (not running)")

    if LOCK_FILE.exists():
        print(f"Lock file: {LOCK_FILE} (present)")
    else:
        print(f"Lock file: {LOCK_FILE} (absent)")

    try:
        r = subprocess.run(["pgrep", "-x", "SystemUIServer"], capture_output=True)
        if r.returncode == 0:
            print("SystemUIServer: running")
        else:
            print("SystemUIServer: NOT running (NSStatusBar will hang!)")
    except Exception as e:
        print(f"SystemUIServer: check failed ({e})")

    try:
        import version
        print(f"Version: {version.__version__}")
    except Exception as e:
        print(f"Version: unknown ({e})")

    bd, source = _read_build_date()
    print(f"Build date: {bd} (from {source})")

    if INSTALLED_APP.exists():
        print(f"Installed: {INSTALLED_APP}")
    else:
        print("Installed: no (run `make release`)")


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
    if not INSTALLED_APP.exists():
        print(f"ERROR: {INSTALLED_APP} not found. Run `make release` first.")
        return 1
    if _find_pids():
        print("NotifyMe is already running, activating existing instance...")
        subprocess.run(["open", "-a", str(INSTALLED_APP)], check=False)
        return 0
    print(f"Starting {INSTALLED_APP}...")
    subprocess.run(["open", "-a", str(INSTALLED_APP)], check=False)
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
        app.setActivationPolicy_(0)
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
        return True

    def switchToAccessory_(self, timer):
        print("[DEBUG] Switching to Accessory policy", flush=True)
        NSApplication.sharedApplication().setActivationPolicy_(1)

        from status_bar import StatusBarController
        self.status_bar = StatusBarController.alloc().initWithApp_(self)
        print("[DEBUG] StatusBarController created", flush=True)

        self.ui_timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self, "tickUI:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.ui_timer, NSRunLoopCommonModes)
        print("[DEBUG] ui_timer created", flush=True)

        self.notify_timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self.status_bar, "checkNotifications:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.notify_timer, NSRunLoopCommonModes)
        print("[DEBUG] notify_timer created", flush=True)

        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "delayedUpdate:", None, False
        )
        print("[DEBUG] delayedUpdate scheduled", flush=True)

    def delayedUpdate_(self, timer):
        try:
            print("[DEBUG] delayedUpdate_ start", flush=True)
            if self.status_bar is not None:
                self.status_bar.update()
            print("[DEBUG] delayedUpdate_ done", flush=True)
        except Exception as e:
            import traceback
            print(f"[DEBUG] delayedUpdate_ error: {e}", flush=True)
            traceback.print_exc()

    def tickUI_(self, timer):
        try:
            if self.status_bar is not None:
                self.status_bar.update()
        except Exception as e:
            import traceback
            print(f"[DEBUG] tickUI_ error: {e}", flush=True)
            traceback.print_exc()

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
        elif cmd == "status":
            _status()
            sys.exit(0)
        elif cmd in ("--help", "-h", "help"):
            print("Usage: notifyme [start|stop|restart|refresh|status|--add-event]")
            sys.exit(0)

    if _already_running_via_launchservices():
        print("NotifyMe is already running (LaunchServices), exiting.", flush=True)
        sys.exit(0)

    lock_file = open(LOCK_FILE, "w")
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
