# dialogs.py
import subprocess
import os
import time
import threading
from datetime import datetime
from AppKit import NSApplication
from calendar_service import get_dialog_message
from config import CONFIG

def escape_applescript_string(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

def show_alarm(events_data):
    if not events_data:
        return
        
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    
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
    safe_text = escape_applescript_string(full_text)
    
    if has_link and first_url:
        safe_url = escape_applescript_string(first_url)
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
    
    # --- ЗВУК ---
    sound_path = CONFIG.get("sound_file", "/System/Library/Sounds/Glass.aiff")
    if not os.path.exists(sound_path):
        sound_path = "/System/Library/Sounds/Glass.aiff"
    
    sound_process = None
    dialog_process = subprocess.Popen(["osascript", "-e", script])
    
    def play_alarm():
        nonlocal sound_process
        if os.path.exists(sound_path):
            while True:
                sound_process = subprocess.Popen(["afplay", sound_path])
                sound_process.wait()
                if dialog_process.poll() is not None:
                    break
                time.sleep(0.5)
    
    threading.Thread(target=play_alarm, daemon=True).start()
    
    # Ждём, пока пользователь не закроет окно
    dialog_process.wait()
    
    # Останавливаем звук
    if sound_process and sound_process.poll() is None:
        sound_process.terminate()
        try:
            sound_process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            sound_process.kill()
            
    # Автозакрытие через 15 минут
    def kill_dialog():
        if dialog_process.poll() is None:
            dialog_process.terminate()
            try:
                dialog_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                dialog_process.kill()
    
    threading.Timer(900, kill_dialog).start()
