# src/app.py
import contextlib
import fcntl
import os
import sys

from AppKit import NSApplication
from Foundation import NSObject, NSTimer

import audio_output  # noqa: F401
from calendar_service import request_calendar_access


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


def main():
    print(f"[DEBUG] sys.argv = {sys.argv}", flush=True)

    if "--add-event" in sys.argv:
        print("[DEBUG] --add-event mode detected", flush=True)
        from add_event_window import main as show_form
        show_form()
        sys.exit(0)

    lock_file_path = "/tmp/notifyme.lock"
    lock_file = open(lock_file_path, "w")  # noqa: SIM115
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:  # mypy/UP024: IOError — алиас OSError
        print("NotifyMe is already running.")
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
            os.remove(lock_file_path)


if __name__ == "__main__":
    main()
