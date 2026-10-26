# app.py
import sys

# Require Python 3.13 or newer
if sys.version_info < (3, 13):
    print("Error: NotifyMe requires Python 3.13 or newer.")
    print(f"Current version: {sys.version.split()[0]}")
    sys.exit(1)

import rumps
import subprocess
import os
import time
import fcntl
import objc
import threading
import queue
from datetime import datetime, timedelta

from AppKit import (
    NSMenu, NSMenuItem, NSApplication, NSColor, NSAttributedString,
    NSForegroundColorAttributeName, NSTimer, NSRunLoop, NSRunLoopCommonModes,
    NSImage
)
from Foundation import NSObject

from calendar_service import (
    request_calendar_access,
    get_upcoming_events,
    get_week_events,
    get_dialog_message
)
from state_manager import load_state, save_state
from utils import get_gradient_color, get_status_color, format_time_delta, format_event_date
from calendar_icon import generate_hourglass_icon

class MenuItemHandler(NSObject):
    def initWithURL_(self, url):
        self = objc.super(MenuItemHandler, self).init()
        if self is None:
            return None
        self.url = url
        return self

    def openURL_(self, sender):
        if self.url:
            subprocess.Popen(["open", self.url])

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
            30.0, self, "trigger_notification_check:", None, True
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
            self.show_notification_on_main(events_data)
        except queue.Empty:
            pass

    def trigger_update(self, sender):
        if self.is_updating:
            return
        self.is_updating = True
        threading.Thread(target=self._background_update, daemon=True).start()

    def _background_update(self):
        try:
            events = get_upcoming_events(self.store)
            week_events = get_week_events(self.store)
            self.update_queue.put((events, week_events))
        except Exception as e:
            print(f"Background thread error (update): {e}")
            self.is_updating = False

    def open_calendar(self, sender):
        subprocess.Popen(["open", "-a", "Calendar"])

    def apply_update(self, data):
        events, week_events = data
        self.is_updating = False
        
        status_text, color = get_status_color(events)
        self.last_status = (status_text, color)
        self.title = f" {status_text}" if status_text else ""
        
        self.menu.clear()
        self.menu_handlers = []
        
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
        future = [ev for ev in events if ev["start"] > now]
        finished = [ev for ev in events if ev["end"] < now]
        
        def add_colored_item(title, color, enabled=True, url=None):
            item = rumps.MenuItem(title)
            attrs = {NSForegroundColorAttributeName: color}
            attr_str = NSAttributedString.alloc().initWithString_attributes_(title, attrs)
            item._menuitem.setAttributedTitle_(attr_str)
            item._menuitem.setEnabled_(enabled)
            
            if url and enabled:
                handler = MenuItemHandler.alloc().initWithURL_(url)
                item._menuitem.setTarget_(handler)
                item._menuitem.setAction_("openURL:")
                self.menu_handlers.append(handler)
            
            self.menu.add(item)
        
        if ongoing:
            add_colored_item("— Ongoing —", NSColor.grayColor(), enabled=False)
            for ev in ongoing:
                minutes_ago = int((now - ev["start"]).total_seconds() // 60)
                item_color = get_gradient_color(minutes_ago, is_ongoing=True)
                title = f"{ev['start'].strftime('%H:%M')} | {ev['title']} | {format_time_delta(minutes_ago)}"
                add_colored_item(title, item_color, url=ev["url"])
        
        if future:
            if ongoing:
                self.menu.add(rumps.separator)
            add_colored_item("— Upcoming (Today) —", NSColor.grayColor(), enabled=False)
            for ev in future:
                delta = (ev["start"] - now).total_seconds() / 60.0
                item_color = get_gradient_color(delta, is_ongoing=False)
                title = f"{ev['start'].strftime('%H:%M')} | {ev['title']} | In {format_time_delta(delta)}"
                add_colored_item(title, item_color, url=ev["url"])
        
        if finished:
            if ongoing or future:
                self.menu.add(rumps.separator)
            add_colored_item("— Finished (Today) —", NSColor.grayColor(), enabled=False)
            for ev in finished:
                minutes_ago = int((now - ev["end"]).total_seconds() // 60)
                title = f"{ev['start'].strftime('%H:%M')} | {ev['title']} | Ended {format_time_delta(minutes_ago)} ago"
                add_colored_item(title, NSColor.grayColor(), enabled=False)
        
        if not events:
            add_colored_item("No events today", NSColor.grayColor(), enabled=False)
        
        # Фильтруем события на неделю: исключаем всё, что начинается сегодня
        filtered_week_events = [ev for ev in week_events if ev["start"] >= tomorrow]
        
        if filtered_week_events:
            self.menu.add(rumps.separator)
            add_colored_item("— Next 7 Days —", NSColor.grayColor(), enabled=False)
            
            # Берем только первые 10 для отображения
            display_events = filtered_week_events[:10]
            total_events = len(display_events)
            
            for i, ev in enumerate(display_events):
                # Плавный градиент сверху вниз в зависимости от индекса строки
                t = i / (total_events - 1) if total_events > 1 else 0.0
                
                # Начальный цвет (темный фиолетовый): (0.5, 0.3, 0.8)
                # Конечный цвет (светлый сиреневый): (0.85, 0.7, 1.0)
                r = 0.5 + (0.85 - 0.5) * t
                g = 0.3 + (0.7 - 0.3) * t
                b = 0.8 + (1.0 - 0.8) * t
                
                row_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)
                
                date_str = format_event_date(ev['start'], now)
                title = f"{date_str} | {ev['title']}"
                
                add_colored_item(title, row_color, url=ev["url"])
                
            if len(filtered_week_events) > 10:
                add_colored_item(f"... and {len(filtered_week_events) - 10} more", NSColor.grayColor(), enabled=False)
        
        self.menu.add(rumps.separator)
        
        calendar_item = rumps.MenuItem("📅 Calendar", callback=self.open_calendar)
        self.menu.add(calendar_item)
        
        quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)
        self.menu.add(quit_item)

    def trigger_notification_check_(self, sender):
        if self.is_checking:
            return
        self.is_checking = True
        threading.Thread(target=self._background_check, daemon=True).start()

    def _background_check(self):
        try:
            now = datetime.now()
            events = get_upcoming_events(self.store)
            events_to_notify = []
            
            for ev in events:
                delta_minutes = (ev["start"] - now).total_seconds() / 60.0
                if -10 <= delta_minutes <= 5:
                    if ev["id"] not in self.notified_ids:
                        events_to_notify.append(ev)
                        self.notified_ids.add(ev["id"])
            
            if events_to_notify:
                self.notification_queue.put(events_to_notify)
                save_state(self.notified_ids)
            else:
                self.is_checking = False
        except Exception as e:
            print(f"Background thread error (check): {e}")
            self.is_checking = False

    def show_notification_on_main(self, events_data):
        self.is_checking = False
        self.show_notification_fallback(events_data)

    def animate_hourglass(self, sender):
        status_text, color = self.last_status
        is_hot = color[0] > 0.9 and color[1] < 0.5
        
        if not is_hot:
            icon_path = generate_hourglass_icon(color, fill_ratio=1.0, flipped=False, blink=False)
            self.icon = icon_path
            return
        
        if self.anim_state == "pouring":
            self.pour_progress += 0.04
            if self.pour_progress >= 1.0:
                self.pour_progress = 1.0
                self.anim_state = "blinking"
                self.blink_count = 0
            fill_ratio = 1.0 - self.pour_progress
            icon_path = generate_hourglass_icon(color, fill_ratio=fill_ratio, flipped=self.flipped, blink=False)
            self.icon = icon_path
        
        elif self.anim_state == "blinking":
            blink = (self.blink_count % 2 == 0)
            fill_ratio = 0.0
            icon_path = generate_hourglass_icon(color, fill_ratio=fill_ratio, flipped=self.flipped, blink=blink)
            self.icon = icon_path
            self.blink_count += 1
            if self.blink_count >= 4:
                self.anim_state = "flipped"
        
        elif self.anim_state == "flipped":
            self.flipped = not self.flipped
            self.pour_progress = 0.0
            self.anim_state = "pouring"
            fill_ratio = 1.0
            icon_path = generate_hourglass_icon(color, fill_ratio=fill_ratio, flipped=self.flipped, blink=False)
            self.icon = icon_path

    def show_notification_fallback(self, events_data):
        if not events_data:
            return
        
        now = datetime.now()
        lines = []
        first_url = None
        has_link = False
        
        for ev in events_data:
            msg = get_dialog_message(ev["start"], now)
            lines.append(f"{msg}:")
            lines.append(f"  {ev['title']}")
            if ev["url"]:
                has_link = True
                lines.append(f"  🔗 Link available (click 'Open Link' below)")
                if first_url is None:
                    first_url = ev["url"]
            lines.append("")
        
        full_text = "\n".join(lines)
        safe_text = full_text.replace('"', '\\"').replace("'", "\\'")
        
        if has_link and first_url:
            safe_url = first_url.replace('"', '\\"')
            script = f'''
            tell application "System Events"
                activate
                set dialogResult to display dialog "{safe_text}" buttons {{"Close", "Open Link"}} default button "Open Link" with title "⏰ Meeting Reminder" with icon note
                if button returned of dialogResult is "Open Link" then
                    do shell script "open {safe_url}"
                end if
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                activate
                display dialog "{safe_text}" buttons {{"Close"}} default button "Close" with title "⏰ Meeting Reminder" with icon note
            end tell
            '''
        
        sound_process = None
        
        # Запускаем окно (оно блокирует этот поток, пока не нажмут кнопку)
        dialog_process = subprocess.Popen(["osascript", "-e", script])
        
        def play_alarm():
            nonlocal sound_process
            sound_path = "/System/Library/Sounds/Hero.aiff"
            if os.path.exists(sound_path):
                while True:
                    sound_process = subprocess.Popen(["afplay", sound_path])
                    sound_process.wait()
                    if dialog_process.poll() is not None:
                        break
                    time.sleep(0.5)
        
        alarm_thread = threading.Thread(target=play_alarm, daemon=True)
        alarm_thread.start()
        
        # Ждём закрытия окна
        dialog_process.wait()
        
        # Останавливаем звук
        if sound_process and sound_process.poll() is None:
            sound_process.terminate()
            try:
                sound_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                sound_process.kill()
                
        def kill_dialog():
            if dialog_process.poll() is None:
                dialog_process.terminate()
                try:
                    dialog_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    dialog_process.kill()
        
        threading.Timer(900, kill_dialog).start()

if __name__ == "__main__":
    lock_file_path = "/tmp/notifyme.lock"
    lock_file = open(lock_file_path, "w")
    
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("NotifyMe is already running. Exiting second instance.")
        sys.exit(0)
    
    try:
        NotifyMeApp().run()
    finally:
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        try:
            os.remove(lock_file_path)
        except:
            pass
