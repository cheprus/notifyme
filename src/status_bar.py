# src/status_bar.py
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import objc
from AppKit import (
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPasteboard,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSObject

import audio_output
import strings as S
from alarm_utils import _resolve_sound_path_for
from calendar_icon import generate_hourglass_icon
from calendar_service import get_upcoming_events, get_week_events
from config import CONFIG, save_config
from dialogs import show_alarm
from menu_item_view import MenuItemView
from settings import show_settings
from state_manager import load_state, save_state
from ui_utils import format_event_for_clipboard, get_status_color

install_hotkey: Callable[[Any], Any] | None
try:
    from hotkeys import install_hotkey, is_accessibility_granted
    _HAS_HOTKEYS = True
except ImportError as e:
    print(f"[DEBUG] hotkeys not available: {e}", flush=True)
    install_hotkey = None

    def is_accessibility_granted():
        return False

    _HAS_HOTKEYS = False


_PREVIEW_HANDLE: list[Any] = []


def _parse_dnd_until():
    v = CONFIG.get("dnd_until")
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return None


class StatusBarController(NSObject):
    def initWithApp_(self, app):
        self = objc.super(StatusBarController, self).init()
        if self is None:
            return None
        self.app = app
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.menu = NSMenu.alloc().init()
        self.status_item.setMenu_(self.menu)
        self.notified_ids = load_state()
        self.is_checking = False
        self.selected_ids = set()
        self._icon_cache_key = None
        self._icon_path = None
        self._hotkey_monitor = None

        if _HAS_HOTKEYS and install_hotkey is not None and is_accessibility_granted():
            try:
                self._hotkey_monitor = install_hotkey(self.handleHotkey_)
                print("[DEBUG] hotkey installed", flush=True)
            except Exception as e:
                print(f"[DEBUG] hotkey install failed: {e}", flush=True)
        else:
            print("[DEBUG] hotkey not installed: Accessibility not granted", flush=True)

        return self

    def handleHotkey_(self, sender=None):
        print("[DEBUG] Hotkey Cmd+Ctrl+N triggered", flush=True)
        self.addToCalendar_(None)

    def showEventCard_(self, event):
        try:
            from event_card import show_event_card
            show_event_card(event)
        except Exception as e:
            import traceback
            print(f"[DEBUG] show_event_card failed: {e}", flush=True)
            traceback.print_exc()

    def copy_selected_to_clipboard(self):
        now = datetime.now()
        events = get_upcoming_events(self.app.store)
        week_events = get_week_events(self.app.store)
        all_events = events + week_events
        selected_events = [ev for ev in all_events if ev["id"] in self.selected_ids]

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()

        if not selected_events:
            print("[DEBUG] No selected events, clipboard cleared", flush=True)
            return

        text_parts = [format_event_for_clipboard(ev, now) for ev in selected_events]
        full_text = "\n".join(text_parts)
        pb.setString_forType_(full_text, "public.utf8-plain-text")
        print(f"[DEBUG] Copied {len(selected_events)} events", flush=True)

    def playSoundPreview_(self, sender):
        raw = sender.title().replace(S.SETTINGS_CHECK, "").replace(S.SETTINGS_UNCHECK, "").strip()
        path = _resolve_sound_path_for(raw)
        if not path:
            print(f"[DEBUG] Sound not found: {raw}", flush=True)
            return

        while _PREVIEW_HANDLE:
            audio_output.stop_playing(_PREVIEW_HANDLE.pop())

        device = CONFIG.get("sound_output_device", "Default")
        handle = audio_output.play_on_device(path, device, loops=0)
        if handle is not None:
            _PREVIEW_HANDLE.append(handle)
            print(f"[DEBUG] Preview on {device!r}: {raw}", flush=True)
        else:
            subprocess.Popen(["afplay", path])
            print(f"[DEBUG] Preview fallback (system default): {raw}", flush=True)

        CONFIG["sound_file"] = raw
        save_config(CONFIG)

    def openSettings_(self, sender=None):
        try:
            show_settings(store=self.app.store, on_change=self._on_settings_changed)
            print("[DEBUG] Settings window opened", flush=True)
        except Exception as e:
            import traceback
            print(f"[DEBUG] openSettings_ failed: {e}", flush=True)
            traceback.print_exc()

    def _on_settings_changed(self):
        try:
            self._reinstall_hotkey_if_needed()
        except Exception as e:
            print(f"[DEBUG] reinstall hotkey failed: {e}", flush=True)
        self.update()

    def _reinstall_hotkey_if_needed(self):
        """Переустановить hotkey. Звать после Settings/Import/Reset."""
        if not _HAS_HOTKEYS or install_hotkey is None:
            return
        if not is_accessibility_granted():
            return
        if self._hotkey_monitor is not None:
            try:
                from hotkeys import uninstall_hotkey
                uninstall_hotkey()
            except Exception:
                pass
            self._hotkey_monitor = None
        try:
            self._hotkey_monitor = install_hotkey(self.handleHotkey_)
            print("[DEBUG] hotkey reinstalled", flush=True)
        except Exception as e:
            print(f"[DEBUG] hotkey reinstall failed: {e}", flush=True)

    def openAccessibilitySettings_(self, sender):
        try:
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ])
        except Exception as e:
            print(f"[DEBUG] open Accessibility settings failed: {e}", flush=True)

    def toggleDND_(self, sender):
        current = _parse_dnd_until()
        if current is not None and current > datetime.now():
            CONFIG["dnd_until"] = None
            save_config(CONFIG)
            self.update()
            return

        now = datetime.now()
        events = get_upcoming_events(self.app.store)
        ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
        if not ongoing:
            return
        latest_end = max(ev["end"] for ev in ongoing)
        CONFIG["dnd_until"] = latest_end.isoformat()
        save_config(CONFIG)
        self.update()

    def confirmQuit_(self, sender=None):
        """Прямой Quit без NSAlert — menu-bar app не должен «зависать» на подтверждении."""
        print("[DEBUG] confirmQuit_ called", flush=True)
        try:
            from alarm_utils import close_all_alarms
            close_all_alarms()
        except Exception:
            pass
        from AppKit import NSApplication
        NSApplication.sharedApplication().terminate_(None)

    def addToCalendar_(self, sender):
        try:
            from add_event_window import main as show_form
            show_form(as_child=True)
        except Exception as e:
            import traceback
            print(f"[DEBUG] addToCalendar_ failed: {e}", flush=True)
            traceback.print_exc()

    def openCalendar_(self, sender):
        subprocess.Popen(["open", "-a", "Calendar"])

    def update(self):
        try:
            now = datetime.now()
            events = get_upcoming_events(self.app.store)
            week_events = get_week_events(self.app.store)

            status_text, color = get_status_color(events)

            cache_key = (color, 1.0, False, False)
            if cache_key != self._icon_cache_key:
                self._icon_cache_key = cache_key
                self._icon_path = generate_hourglass_icon(color, fill_ratio=1.0, flipped=False, blink=False)
            button = self.status_item.button()
            if button and self._icon_path:
                img = NSImage.alloc().initWithContentsOfFile_(self._icon_path)
                if img:
                    img.setSize_((16, 16))
                    button.setImage_(img)
                dnd = _parse_dnd_until()
                if dnd is not None and dnd > now:
                    button.setTitle_(f" 🔕 {dnd.strftime('%H:%M')}")
                else:
                    button.setTitle_(f" {status_text}")
                button.setImagePosition_(2)

            self.menu.removeAllItems()

            def add_section(title):
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
                item.setEnabled_(False)
                self.menu.addItem_(item)

            def add_event_item(ev, show_date=False):
                item = NSMenuItem.alloc().init()
                view = MenuItemView.alloc().initWithFrame_event_controller_showDate_(
                    NSMakeRect(0, 0, 460, 24), ev, self, show_date
                )
                item.setView_(view)
                self.menu.addItem_(item)

            add_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(S.MENU_NEW_EVENT, "addToCalendar:", "")
            add_item.setTarget_(self)
            self.menu.addItem_(add_item)

            settings_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                S.SETTINGS_TITLE, "openSettings:", ","
            )
            settings_item.setTarget_(self)
            self.menu.addItem_(settings_item)

            dnd = _parse_dnd_until()
            if dnd is not None and dnd > now:
                dnd_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    S.MENU_DND_UNTIL.format(time=dnd.strftime("%H:%M")), "toggleDND:", ""
                )
                dnd_item.setTarget_(self)
                self.menu.addItem_(dnd_item)
            else:
                ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
                if ongoing:
                    dnd_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        S.MENU_DND_UNTIL_END, "toggleDND:", ""
                    )
                    dnd_item.setTarget_(self)
                    self.menu.addItem_(dnd_item)

            open_cal = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(S.MENU_OPEN_CALENDAR, "openCalendar:", "")
            open_cal.setTarget_(self)
            self.menu.addItem_(open_cal)

            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(S.MENU_QUIT, "confirmQuit:", "q")
            quit_item.setTarget_(self)
            self.menu.addItem_(quit_item)

            self.menu.addItem_(NSMenuItem.separatorItem())

            ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
            future = [ev for ev in events if ev["start"] > now]
            finished = [ev for ev in events if ev["end"] < now]

            if ongoing:
                add_section(S.MENU_SECTION_ONGOING)
                for ev in ongoing:
                    add_event_item(ev)
            if future:
                if ongoing:
                    self.menu.addItem_(NSMenuItem.separatorItem())
                add_section(S.MENU_SECTION_UPCOMING)
                for ev in future:
                    add_event_item(ev)
            if finished:
                if ongoing or future:
                    self.menu.addItem_(NSMenuItem.separatorItem())
                add_section(S.MENU_SECTION_FINISHED)
                for ev in finished:
                    add_event_item(ev)

            if not events:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(S.MENU_NO_EVENTS_TODAY, None, "")
                item.setEnabled_(False)
                self.menu.addItem_(item)

            tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_after_tomorrow = tomorrow_start + timedelta(days=1)
            tomorrow_events = [ev for ev in week_events if tomorrow_start <= ev["start"] < day_after_tomorrow]
            if tomorrow_events:
                self.menu.addItem_(NSMenuItem.separatorItem())
                add_section(S.MENU_SECTION_TOMORROW)
                for ev in tomorrow_events:
                    add_event_item(ev, show_date=True)

            next_week_events = [ev for ev in week_events if ev["start"] >= day_after_tomorrow]
            if next_week_events:
                self.menu.addItem_(NSMenuItem.separatorItem())
                add_section(S.MENU_SECTION_NEXT_7_DAYS)
                for ev in next_week_events[:30]:
                    add_event_item(ev, show_date=True)
                if len(next_week_events) > 30:
                    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        S.MENU_MORE_EVENTS.format(n=len(next_week_events) - 30), None, ""
                    )
                    item.setEnabled_(False)
                    self.menu.addItem_(item)
        except Exception as e:
            import traceback
            print(f"[DEBUG] update failed: {e}", flush=True)
            traceback.print_exc()

    def checkNotifications_(self, sender):
        if self.is_checking:
            return
        self.is_checking = True
        try:
            dnd = _parse_dnd_until()
            if dnd is not None and dnd > datetime.now():
                return

            now = datetime.now()
            events = get_upcoming_events(self.app.store)
            notify_before = CONFIG.get("notify_minutes_before", 5)
            notify_after = CONFIG.get("notify_minutes_after", 2)
            hyst = 5.0 / 60.0
            to_notify = []
            for ev in events:
                delta_minutes = (ev["start"] - now).total_seconds() / 60.0
                if (
                    -notify_after <= delta_minutes <= notify_before + hyst
                    and ev["id"] not in self.notified_ids
                ):
                    to_notify.append(ev)
                    self.notified_ids.add(ev["id"])
            if to_notify:
                show_alarm(to_notify)
                save_state(self.notified_ids)
        except Exception as e:
            print(f"[DEBUG] Notification check error: {e}", flush=True)
        finally:
            self.is_checking = False
