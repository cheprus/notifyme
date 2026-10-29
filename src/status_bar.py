# src/status_bar.py
import objc, subprocess, os, sys
from datetime import datetime, timedelta
from Foundation import NSDate, NSTimer, NSObject
from AppKit import (
    NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem,
    NSImage, NSMakeRect, NSPasteboard,
    NSAlert, NSTextField, NSApplication, NSStatusWindowLevel
)
from menu_item_view import MenuItemView
from calendar_service import (
    get_upcoming_events, get_week_events, create_event_via_applescript, list_calendars
)
from calendar_icon import generate_hourglass_icon
from ui_utils import (
    get_status_color, get_event_color, format_event_for_clipboard
)
from config import (
    CONFIG, save_config, AVAILABLE_TIMEZONES, AVAILABLE_SOUNDS,
    NOTIFY_BEFORE_PRESETS
)
from state_manager import load_state, save_state
from dialogs import show_alarm, close_all_alarms, _get_audio_outputs


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
        return self

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
        sound_name = sender.title().replace("✓ ", "").replace("   ", "").strip()
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
        if os.path.exists(sound_path):
            subprocess.Popen(["afplay", sound_path])
            CONFIG["sound_file"] = sound_path
            save_config(CONFIG)

    def handleNotifyTime_(self, sender):
        tag = sender.tag()
        CONFIG["notify_minutes_before"] = tag
        save_config(CONFIG)
        print(f"[DEBUG] Notify time set to {tag} min", flush=True)
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
        try:
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
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

    def clearHistory_(self, sender):
        try:
            close_all_alarms()
        except Exception as e:
            print(f"[DEBUG] close_all_alarms failed: {e}", flush=True)
        self.notified_ids.clear()
        save_state(self.notified_ids)
        self.update()

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

    def _build_timezone_submenu(self, current, action_selector):
        sub = NSMenu.alloc().init()

        flat = ["Local", "UTC"]
        for tz in flat:
            prefix = "✓ " if tz == current else "   "
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"{prefix}{tz}", action_selector, ""
            )
            it.setRepresentedObject_(tz)
            it.setTarget_(self)
            sub.addItem_(it)

        if current and current not in flat:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"✓ {current}", action_selector, ""
            )
            it.setRepresentedObject_(current)
            it.setTarget_(self)
            sub.addItem_(it)

        sub.addItem_(NSMenuItem.separatorItem())

        regions = {}
        for tz in AVAILABLE_TIMEZONES:
            if tz in ("Local", "UTC") or tz == current:
                continue
            if "/" in tz:
                region = tz.split("/", 1)[0]
            else:
                region = "Other"
            regions.setdefault(region, []).append(tz)

        preferred = ["Europe", "Asia", "America", "Africa", "Australia", "Pacific", "Atlantic", "Indian"]
        ordered = []
        for r in preferred:
            if r in regions:
                ordered.append(r)
        for r in sorted(regions.keys()):
            if r not in ordered:
                ordered.append(r)

        for region in ordered:
            region_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"{region} ({len(regions[region])})", None, ""
            )
            region_sub = NSMenu.alloc().init()
            for tz in regions[region]:
                it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    tz, action_selector, ""
                )
                it.setRepresentedObject_(tz)
                it.setTarget_(self)
                region_sub.addItem_(it)
            region_item.setSubmenu_(region_sub)
            sub.addItem_(region_item)

        return sub

    def _build_notify_before_submenu(self):
        sub = NSMenu.alloc().init()
        current_min = CONFIG.get("notify_minutes_before", 5)

        for mins in NOTIFY_BEFORE_PRESETS:
            if mins == 0:
                label = "At start"
            elif mins % 60 == 0:
                label = f"{mins // 60}h"
            else:
                label = f"{mins} min"
            prefix = "✓ " if mins == current_min else "   "
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"{prefix}{label}", "handleNotifyTime:", ""
            )
            it.setTag_(mins)
            it.setTarget_(self)
            sub.addItem_(it)

        if current_min not in NOTIFY_BEFORE_PRESETS:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"✓ {current_min} min (custom)", "handleNotifyTime:", ""
            )
            it.setTag_(current_min)
            it.setTarget_(self)
            sub.addItem_(it)

        sub.addItem_(NSMenuItem.separatorItem())
        it_custom = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Custom…", "handleNotifyCustom:", ""
        )
        it_custom.setTarget_(self)
        sub.addItem_(it_custom)

        return sub

    def _build_settings_menu(self):
        settings_menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⚙️ Settings", None, "")
        settings_sub = NSMenu.alloc().init()

        sound_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔊 Sound", None, "")
        sound_sub = NSMenu.alloc().init()
        current_sound = os.path.basename(CONFIG.get("sound_file", "")).replace(".aiff", "")
        for snd in AVAILABLE_SOUNDS:
            prefix = "✓ " if snd == current_sound else "   "
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(f"{prefix}{snd}", "playSoundPreview:", "")
            it.setTarget_(self)
            sound_sub.addItem_(it)
        sound_item.setSubmenu_(sound_sub)
        settings_sub.addItem_(sound_item)

        time_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⏱ Notify Before", None, "")
        time_item.setSubmenu_(self._build_notify_before_submenu())
        settings_sub.addItem_(time_item)

        tz_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🌍 Timezone (display)", None, "")
        current_tz = CONFIG.get("display_timezone", "Local")
        tz_item.setSubmenu_(self._build_timezone_submenu(current_tz, "handleDisplayTimezone:"))
        settings_sub.addItem_(tz_item)

        tz_copy_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📋 Timezone (copy)", None, "")
        current_copy_tz = CONFIG.get("copy_timezone", "Local")
        tz_copy_item.setSubmenu_(self._build_timezone_submenu(current_copy_tz, "handleCopyTimezone:"))
        settings_sub.addItem_(tz_copy_item)

        cal_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📅 Calendar", None, "")
        cal_sub = NSMenu.alloc().init()
        current_cal = CONFIG.get("target_calendar_name", "") or ""
        try:
            cals = list_calendars(self.app.store) if self.app.store else []
            cal_names = [c.get("title") for c in cals if c.get("title")]
        except Exception:
            cal_names = []

        if current_cal and current_cal not in cal_names:
            print(f"[DEBUG] Configured calendar {current_cal!r} not found — using (default)", flush=True)
            current_cal = ""

        prefix = "✓ " if not current_cal else "   "
        it_default = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}(default)", "handleCalendar:", ""
        )
        it_default.setRepresentedObject_("")
        it_default.setTarget_(self)
        cal_sub.addItem_(it_default)

        for cal_name in cal_names:
            prefix = "✓ " if cal_name == current_cal else "   "
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"{prefix}{cal_name}", "handleCalendar:", ""
            )
            it.setRepresentedObject_(cal_name)
            it.setTarget_(self)
            cal_sub.addItem_(it)

        cal_item.setSubmenu_(cal_sub)
        settings_sub.addItem_(cal_item)

        out_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔈 Output", None, "")
        out_sub = NSMenu.alloc().init()
        current_out = CONFIG.get("sound_output_device", "Default")
        try:
            outputs = _get_audio_outputs()
        except Exception:
            outputs = ["Default"]
        for dev in outputs:
            prefix = "✓ " if dev == current_out else "   "
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(f"{prefix}{dev}", "handleAudioOutput:", "")
            it.setRepresentedObject_(dev)
            it.setTarget_(self)
            out_sub.addItem_(it)
        out_item.setSubmenu_(out_sub)
        settings_sub.addItem_(out_item)

        settings_menu.setSubmenu_(settings_sub)
        return settings_menu

    def update(self):
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

        self.menu.addItem_(self._build_settings_menu())

        open_cal = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📅 Open Calendar", "openCalendar:", "")
        open_cal.setTarget_(self)
        self.menu.addItem_(open_cal)

        clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔄 Clear History", "clearHistory:", "")
        clear_item.setTarget_(self)
        self.menu.addItem_(clear_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "q")
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
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(f"... and {len(next_week_events) - 30} more", None, "")
                item.setEnabled_(False)
                self.menu.addItem_(item)

    def checkNotifications_(self, sender):
        if self.is_checking:
            return
        self.is_checking = True
        try:
            now = datetime.now()
            events = get_upcoming_events(self.app.store)
            notify_before = CONFIG.get("notify_minutes_before", 5)
            hyst = 5.0 / 60.0
            to_notify = []
            for ev in events:
                delta_minutes = (ev["start"] - now).total_seconds() / 60.0
                if -2.0 <= delta_minutes <= notify_before + hyst:
                    if ev["id"] not in self.notified_ids:
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
