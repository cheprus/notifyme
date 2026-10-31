# src/status_bar.py
import contextlib
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import objc
from AppKit import (
    NSAlert,
    NSApplication,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPasteboard,
    NSStatusBar,
    NSStatusWindowLevel,
    NSTextField,
    NSVariableStatusItemLength,
)
from Foundation import NSObject

import audio_output
from alarm_utils import _resolve_sound_path_for, close_all_alarms
from calendar_icon import generate_hourglass_icon
from calendar_service import get_upcoming_events, get_week_events
from config import CONFIG, save_config
from dialogs import show_alarm
from menu_builders import build_settings_menu
from menu_item_view import MenuItemView
from state_manager import load_state, save_state
from ui_utils import format_event_for_clipboard, get_status_color

# install_hotkey может быть None, если модуль hotkeys недоступен
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


# Удерживать preview-handle, пока играет, иначе AVAudioEngine соберётся GC.
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
        raw = sender.title().replace("✓ ", "").replace("   ", "").strip()
        path = _resolve_sound_path_for(raw)
        if not path:
            print(f"[DEBUG] Sound not found: {raw}", flush=True)
            return

        # Остановить предыдущий preview, если ещё играет
        while _PREVIEW_HANDLE:
            audio_output.stop_playing(_PREVIEW_HANDLE.pop())

        device = CONFIG.get("sound_output_device", "Default")
        handle = audio_output.play_on_device(path, device, loops=0)
        if handle is not None:
            _PREVIEW_HANDLE.append(handle)
            print(f"[DEBUG] Preview on {device!r}: {raw}", flush=True)
        else:
            # Фолбэк: системный дефолт
            subprocess.Popen(["afplay", path])
            print(f"[DEBUG] Preview fallback (system default): {raw}", flush=True)

        CONFIG["sound_file"] = raw
        save_config(CONFIG)

    def handleNotifyTime_(self, sender):
        tag = sender.tag()
        CONFIG["notify_minutes_before"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Notify Before set to {tag} min", flush=True)
        self.update()

    def handleNotifyAfter_(self, sender):
        tag = sender.tag()
        CONFIG["notify_minutes_after"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Notify After set to {tag} min", flush=True)
        self.update()

    def handleSnoozeTime_(self, sender):
        tag = sender.tag()
        CONFIG["snooze_minutes"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Snooze set to {tag} min", flush=True)
        self.update()

    def handleNotifyCustom_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Notify Before")
        alert.setInformativeText_("Minutes before the event (0–1440):")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 200, 24))
        field.setStringValue_(str(CONFIG.get("notify_minutes_before", 5)))
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)

        alert.window().setLevel_(NSStatusWindowLevel)
        with contextlib.suppress(Exception):
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        alert.window().makeKeyAndOrderFront_(None)

        if alert.runModal() == 1000:
            try:
                val = int(float(field.stringValue().strip()))
                val = max(0, min(val, 24 * 60))
                CONFIG["notify_minutes_before"] = val
                save_config(CONFIG)
                print(f"[DEBUG] Notify Before set to {val} min (custom)", flush=True)
                self.update()
            except ValueError:
                print(f"[DEBUG] Invalid custom value: {field.stringValue()!r}", flush=True)

    def handleAutoClose_(self, sender):
        tag = sender.tag()
        CONFIG["auto_close_minutes"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Auto-close set to {tag} min", flush=True)
        self.update()

    def handlePulseOn_(self, sender):
        tag = sender.tag()
        CONFIG["alarm_sound_on_seconds"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Pulse ON set to {tag} sec", flush=True)
        self.update()

    def handlePulseOff_(self, sender):
        tag = sender.tag()
        CONFIG["alarm_sound_off_seconds"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Pulse OFF set to {tag} sec", flush=True)
        self.update()

    def handleDisplayTimezone_(self, sender):
        tz = sender.representedObject()
        if tz is not None:
            CONFIG["display_timezone"] = str(tz)
            save_config(CONFIG)
            print(f"[DEBUG] Display timezone set to {tz}", flush=True)
            self.update()

    def handleCopyTimezone_(self, sender):
        tz = sender.representedObject()
        if tz is not None:
            CONFIG["copy_timezone"] = str(tz)
            save_config(CONFIG)
            print(f"[DEBUG] Copy timezone set to {tz}", flush=True)

    def handleCalendar_(self, sender):
        cal_name = sender.representedObject()
        if cal_name is None:
            cal_name = ""
        CONFIG["target_calendar_name"] = str(cal_name)
        save_config(CONFIG)
        print(f"[DEBUG] Target calendar set to {cal_name!r}", flush=True)

    def handleAudioOutput_(self, sender):
        dev = sender.representedObject()
        if dev is not None:
            CONFIG["sound_output_device"] = str(dev)
            save_config(CONFIG)
            print(f"[DEBUG] Audio output set to {dev}", flush=True)

    def openAccessibilitySettings_(self, sender):
        try:
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ])
            print("[DEBUG] Opened Accessibility settings", flush=True)
        except Exception as e:
            print(f"[DEBUG] open Accessibility settings failed: {e}", flush=True)

    def toggleDND_(self, sender):
        current = _parse_dnd_until()
        if current is not None and current > datetime.now():
            CONFIG["dnd_until"] = None
            save_config(CONFIG)
            print("[DEBUG] DND disabled", flush=True)
            self.update()
            return

        now = datetime.now()
        events = get_upcoming_events(self.app.store)
        ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
        if not ongoing:
            print("[DEBUG] DND: no ongoing event", flush=True)
            return
        latest_end = max(ev["end"] for ev in ongoing)
        CONFIG["dnd_until"] = latest_end.isoformat()
        save_config(CONFIG)
        print(f"[DEBUG] DND until {latest_end}", flush=True)
        self.update()

    def clearHistory_(self, sender):
        try:
            close_all_alarms()
        except Exception as e:
            print(f"[DEBUG] close_all_alarms failed: {e}", flush=True)
        self.notified_ids.clear()
        save_state(self.notified_ids)
        self.update()

    def toggleIncludeNotes_(self, sender):
        new_val = not CONFIG.get("include_notes_in_copy", False)
        CONFIG["include_notes_in_copy"] = new_val
        save_config(CONFIG)
        print(f"[DEBUG] include_notes_in_copy: {new_val}", flush=True)
        self.update()

    def confirmQuit_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Quit NotifyMe?")
        alert.setInformativeText_("Alarms will stop working until you launch the app again.")
        alert.addButtonWithTitle_("Quit")
        alert.addButtonWithTitle_("Cancel")
        alert.setAlertStyle_(1)

        alert.window().setLevel_(NSStatusWindowLevel)
        with contextlib.suppress(Exception):
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        alert.window().makeKeyAndOrderFront_(None)

        if alert.runModal() == 1000:
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

            add_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("➕ New event", "addToCalendar:", "")
            add_item.setTarget_(self)
            self.menu.addItem_(add_item)

            self.menu.addItem_(build_settings_menu(
                self,
                is_accessibility_granted=is_accessibility_granted if _HAS_HOTKEYS else None,
                has_hotkeys=_HAS_HOTKEYS,
            ))

            dnd = _parse_dnd_until()
            if dnd is not None and dnd > now:
                dnd_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    f"🔕 DND until {dnd.strftime('%H:%M')}", "toggleDND:", ""
                )
                dnd_item.setTarget_(self)
                self.menu.addItem_(dnd_item)
            else:
                ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
                if ongoing:
                    dnd_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        "🔕 DND until current event ends", "toggleDND:", ""
                    )
                    dnd_item.setTarget_(self)
                    self.menu.addItem_(dnd_item)

            open_cal = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📅 Open Calendar", "openCalendar:", "")
            open_cal.setTarget_(self)
            self.menu.addItem_(open_cal)

            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "confirmQuit:", "q")
            quit_item.setTarget_(self)
            self.menu.addItem_(quit_item)

            self.menu.addItem_(NSMenuItem.separatorItem())

            ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
            future = [ev for ev in events if ev["start"] > now]
            finished = [ev for ev in events if ev["end"] < now]

            if ongoing:
                add_section("— Ongoing —")
                for ev in ongoing:
                    add_event_item(ev)
            if future:
                if ongoing:
                    self.menu.addItem_(NSMenuItem.separatorItem())
                add_section("— Upcoming —")
                for ev in future:
                    add_event_item(ev)
            if finished:
                if ongoing or future:
                    self.menu.addItem_(NSMenuItem.separatorItem())
                add_section("— Finished —")
                for ev in finished:
                    add_event_item(ev)

            if not events:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("No events today", None, "")
                item.setEnabled_(False)
                self.menu.addItem_(item)

            tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_after_tomorrow = tomorrow_start + timedelta(days=1)
            tomorrow_events = [ev for ev in week_events if tomorrow_start <= ev["start"] < day_after_tomorrow]
            if tomorrow_events:
                self.menu.addItem_(NSMenuItem.separatorItem())
                add_section("— Tomorrow —")
                for ev in tomorrow_events:
                    add_event_item(ev, show_date=True)

            next_week_events = [ev for ev in week_events if ev["start"] >= day_after_tomorrow]
            if next_week_events:
                self.menu.addItem_(NSMenuItem.separatorItem())
                add_section("— Next 7 Days —")
                for ev in next_week_events[:30]:
                    add_event_item(ev, show_date=True)
                if len(next_week_events) > 30:
                    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        f"... and {len(next_week_events) - 30} more", None, ""
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
                print(f"[DEBUG] Notifying {len(to_notify)} events", flush=True)
                show_alarm(to_notify)
                save_state(self.notified_ids)
        except Exception as e:
            print(f"[DEBUG] Notification check error: {e}", flush=True)
        finally:
            self.is_checking = False
