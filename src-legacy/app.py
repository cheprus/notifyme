# src/app.py
import sys
if sys.version_info < (3, 13):
    print("Error: NotifyMe requires Python 3.13 or newer.")
    sys.exit(1)

import rumps
import subprocess
import os
import fcntl
import objc
import threading
import queue
from datetime import datetime, timedelta

from AppKit import (
    NSColor, NSAttributedString, NSForegroundColorAttributeName, 
    NSTimer, NSRunLoop, NSRunLoopCommonModes, NSImage, NSPasteboard
)
from Foundation import NSObject

from config import CONFIG, save_config
from calendar_service import request_calendar_access, get_upcoming_events, get_week_events
from state_manager import load_state, save_state
from calendar_icon import generate_hourglass_icon
from dialogs import show_alarm
from ui_utils import (
    get_gradient_color, get_status_color, format_event_line, 
    get_week_gradient_color, format_event_date, format_time_delta
)

class MenuItemHandler(NSObject):
    def initWithURL_(self, url):
        self = objc.super(MenuItemHandler, self).init()
        if self is None: return None
        self.url = url
        return self

    def openURL_(self, sender):
        if self.url: subprocess.Popen(["open", self.url])

class NotifyMeApp(rumps.App):
    def __init__(self):
        super(NotifyMeApp, self).__init__("", quit_button=None)
        
        self.store = request_calendar_access()
        self.notified_ids = load_state()
        self.menu_handlers = []
        
        self.is_updating = False
        self.is_checking = False
        
        self.update_queue = queue.Queue()
        self.notification_queue = queue.Queue()
        
        self.last_status = ("No events", (0.2, 0.8, 0.2))
        
        self.anim_state = "pouring"
        self.pour_progress = 0.0
        self.blink_count = 0
        self.flipped = False
        
        self.menu = []
        
        self.status_timer = rumps.Timer(self.trigger_update, 5)
        self.status_timer.start()
        
        self.queue_timer = rumps.Timer(self.process_queues, 0.1)
        self.queue_timer.start()
        
        self.notify_timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            10.0, self, "trigger_notification_check:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.notify_timer, NSRunLoopCommonModes)
        
        self.animation_timer = rumps.Timer(self.animate_hourglass, 0.2)
        self.animation_timer.start()
        
        self.trigger_update(None)

    def process_queues(self, sender):
        try:
            data = self.update_queue.get_nowait()
            self.apply_update(data)
        except queue.Empty:
            pass
        
        try:
            events_data = self.notification_queue.get_nowait()
            self.is_checking = False
            threading.Thread(target=show_alarm, args=(events_data,), daemon=True).start()
        except queue.Empty:
            pass

    def trigger_update(self, sender):
        if self.is_updating: return
        self.is_updating = True
        threading.Thread(target=self._background_update, daemon=True).start()

    def _background_update(self):
        try:
            events = get_upcoming_events(self.store)
            week_events = get_week_events(self.store)
            self.update_queue.put((events, week_events))
        except Exception as e:
            print(f"Background error: {e}")
            self.is_updating = False

    def open_calendar(self, sender):
        subprocess.Popen(["open", "-a", "Calendar"])

    def clear_history(self, sender):
        self.notified_ids.clear()
        save_state(self.notified_ids)
        self.trigger_update(None)

    def play_sound_preview(self, sender, sound_name):
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
        if os.path.exists(sound_path):
            subprocess.Popen(["afplay", sound_path])
            CONFIG["sound_file"] = sound_path
            save_config(CONFIG)

    def copy_event_to_clipboard(self, sender, event):
        now = datetime.now()
        start = event["start"]
        end = event["end"]
        url = event["url"]
        title = event["title"]
        
        days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        months_ru = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
        
        day_str = days_ru[start.weekday()]
        month_str = months_ru[start.month - 1]
        date_str = f"{day_str}, {start.day} {month_str}, {start.strftime('%H:%M')} MSK"
        
        delta = start - now
        delta_minutes = delta.total_seconds() / 60.0
        
        if delta_minutes > 0:
            time_left = f"через {format_time_delta(delta_minutes)}"
        elif now <= end:
            time_left = "идёт сейчас"
        else:
            time_left = "завершилась"
            
        text = f"📅 Тема: {title}\n"
        text += f"🕒 {date_str} ({time_left})\n"
        if url:
            text += f"🔗 {url}\n"
            
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, "public.utf8-plain-text")
        print(f"[DEBUG] Copied to clipboard: {text}")

    def apply_update(self, data):
        events, week_events = data
        self.is_updating = False
        
        status_text, color = get_status_color(events)
        self.last_status = (status_text, color)
        self.title = f" {status_text}" if status_text else ""
        
        self.menu.clear()
        self.menu_handlers = []
        
        now = datetime.now()
        
        ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
        future = [ev for ev in events if ev["start"] > now]
        finished = [ev for ev in events if ev["end"] < now]
        
        def add_event_item(ev, line_text, color, is_active=True):
            item = rumps.MenuItem(line_text)
            
            attrs = {NSForegroundColorAttributeName: color}
            item._menuitem.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(line_text, attrs))
            
            if is_active:
                if ev["url"]:
                    handler = MenuItemHandler.alloc().initWithURL_(ev["url"])
                    item._menuitem.setTarget_(handler)
                    item._menuitem.setAction_("openURL:")
                    self.menu_handlers.append(handler)
                
                # Подменю с Copy Info (без Actions)
                sub = rumps.MenuItem("...")
                copy_item = rumps.MenuItem("Copy Info", callback=lambda sender, e=ev: self.copy_event_to_clipboard(sender, e))
                sub.add(copy_item)
                item.add(sub)
            else:
                item._menuitem.setEnabled_(False)
                
            self.menu.add(item)
        
        if ongoing:
            header = rumps.MenuItem("— Ongoing —")
            header.set_callback(None)
            self.menu.add(header)
            for ev in ongoing:
                add_event_item(ev, format_event_line(ev, now, is_ongoing=True), get_gradient_color((now - ev['start']).total_seconds() / 60, True))
        
        if future:
            if ongoing: self.menu.add(rumps.separator)
            header = rumps.MenuItem("— Upcoming (Today) —")
            header.set_callback(None)
            self.menu.add(header)
            for ev in future:
                delta = (ev['start'] - now).total_seconds() / 60
                add_event_item(ev, format_event_line(ev, now), get_gradient_color(delta, False))
        
        if finished:
            if ongoing or future: self.menu.add(rumps.separator)
            header = rumps.MenuItem("— Finished (Today) —")
            header.set_callback(None)
            self.menu.add(header)
            for ev in finished:
                add_event_item(ev, format_event_line(ev, now, is_finished=True), NSColor.grayColor(), is_active=False)
        
        if not events:
            self.menu.add(rumps.MenuItem("No events today"))
        
        tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_after_tomorrow = tomorrow_start + timedelta(days=1)
        
        tomorrow_events = [ev for ev in week_events if tomorrow_start <= ev["start"] < day_after_tomorrow]
        if tomorrow_events:
            self.menu.add(rumps.separator)
            header = rumps.MenuItem("— Tomorrow —")
            header.set_callback(None)
            self.menu.add(header)
            tomorrow_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.75, 0.6, 0.95, 1.0)
            for ev in tomorrow_events:
                title = f"{ev['start'].strftime('%H:%M')} · {ev['title']}"
                add_event_item(ev, title, tomorrow_color)

        next_week_events = [ev for ev in week_events if ev["start"] >= day_after_tomorrow]
        if next_week_events:
            self.menu.add(rumps.separator)
            header = rumps.MenuItem("— Next 7 Days —")
            header.set_callback(None)
            self.menu.add(header)
            display_events = next_week_events[:10]
            total = len(display_events)
            for i, ev in enumerate(display_events):
                date_str = format_event_date(ev['start'], now)
                title = f"{date_str} · {ev['title']}"
                add_event_item(ev, title, get_week_gradient_color(i, total))
            if len(next_week_events) > 10:
                self.menu.add(rumps.MenuItem(f"... and {len(next_week_events) - 10} more"))
        
        self.menu.add(rumps.separator)
        
        sound_menu = rumps.MenuItem("🔊 Sound")
        available_sounds = ["Glass", "Hero", "Ping", "Sosumi", "Submarine", "Tink", "Basso", "Funk"]
        current_sound = os.path.basename(CONFIG.get("sound_file", "")).replace(".aiff", "")
        
        for snd in available_sounds:
            prefix = "✓ " if snd == current_sound else "   "
            item = rumps.MenuItem(f"{prefix}{snd}", callback=lambda sender, s=snd: self.play_sound_preview(sender, s))
            sound_menu.add(item)
        self.menu.add(sound_menu)
        
        self.menu.add(rumps.MenuItem("📅 Calendar", callback=self.open_calendar))
        self.menu.add(rumps.MenuItem("🔄 Clear History", callback=self.clear_history))
        self.menu.add(rumps.separator)
        
        quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)
        exit_icon_path = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/AlertStopIcon.icns"
        if os.path.exists(exit_icon_path):
            img = NSImage.alloc().initWithContentsOfFile_(exit_icon_path)
            img.setSize_((16, 16))
            quit_item._menuitem.setImage_(img)
        else:
            quit_item.title = "🚪 Quit"
        self.menu.add(quit_item)

    def trigger_notification_check_(self, sender):
        if self.is_checking: return
        self.is_checking = True
        threading.Thread(target=self._background_check, daemon=True).start()

    def _background_check(self):
        try:
            state_file = os.path.expanduser("~/.notifyme/state.json")
            if not os.path.exists(state_file) and self.notified_ids:
                self.notified_ids.clear()

            now = datetime.now()
            events = get_upcoming_events(self.store)
            
            events_to_notify = []
            notify_before = CONFIG.get("notify_minutes_before", 5)
            
            for ev in events:
                delta_minutes = (ev["start"] - now).total_seconds() / 60.0
                if -2 <= delta_minutes <= notify_before:
                    if ev["id"] not in self.notified_ids:
                        events_to_notify.append(ev)
                        self.notified_ids.add(ev["id"])
            
            if events_to_notify:
                self.notification_queue.put(events_to_notify)
                save_state(self.notified_ids)
            else:
                self.is_checking = False
        except Exception as e:
            print(f"Background error: {e}")
            self.is_checking = False

    def animate_hourglass(self, sender):
        status_text, color = self.last_status
        is_hot = color[0] > 0.9 and color[1] < 0.5
        
        if not is_hot:
            self.icon = generate_hourglass_icon(color, fill_ratio=1.0, flipped=False, blink=False)
            return
        
        if self.anim_state == "pouring":
            self.pour_progress += 0.04
            if self.pour_progress >= 1.0:
                self.pour_progress = 1.0
                self.anim_state = "blinking"
                self.blink_count = 0
            self.icon = generate_hourglass_icon(color, fill_ratio=1.0 - self.pour_progress, flipped=self.flipped)
        
        elif self.anim_state == "blinking":
            blink = (self.blink_count % 2 == 0)
            self.icon = generate_hourglass_icon(color, fill_ratio=0.0, flipped=self.flipped, blink=blink)
            self.blink_count += 1
            if self.blink_count >= 4:
                self.anim_state = "flipped"
        
        elif self.anim_state == "flipped":
            self.flipped = not self.flipped
            self.pour_progress = 0.0
            self.anim_state = "pouring"
            self.icon = generate_hourglass_icon(color, fill_ratio=1.0, flipped=self.flipped)

if __name__ == "__main__":
    lock_file_path = "/tmp/notifyme.lock"
    lock_file = open(lock_file_path, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        sys.exit(0)
    try:
        NotifyMeApp().run()
    finally:
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        try: os.remove(lock_file_path)
        except: pass
