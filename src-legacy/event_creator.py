# event_creator.py
import subprocess
import re
import threading
from datetime import datetime, timedelta
from AppKit import NSPasteboard

try:
    import dateparser
except ImportError:
    print("[ERROR] dateparser is not installed. Run: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pip install dateparser")
    dateparser = None

try:
    import EventKit
    from Foundation import NSDate, NSURL
except ImportError:
    print("[ERROR] EventKit not found.")
    exit(1)

# --- 1. Работа с буфером обмена ---

def get_clipboard_text():
    print("[DEBUG] Reading clipboard...")
    pb = NSPasteboard.generalPasteboard()
    text = pb.stringForType_("public.utf8-plain-text")
    if text:
        print(f"[DEBUG] Clipboard text length: {len(text)}")
        if len(text) < 100:
            print("[WARN] Clipboard text is very short. Did you copy the whole email?")
        return text.strip()
    print("[DEBUG] Clipboard is empty.")
    return None

# --- 2. Извлечение домена ---

def get_organizer_domain(email):
    """Извлекает основное имя домена (например, mts из noir74@mts.ru)."""
    if not email or '@' not in email:
        return ""
    domain = email.split('@')[1]
    parts = domain.split('.')

    known_zones = {'ru', 'com', 'net', 'org', 'io', 'co', 'gov', 'edu', 'info', 'biz'}

    if len(parts) >= 2 and parts[-1].lower() in known_zones:
        if len(parts) >= 3 and parts[-2].lower() in known_zones:
            return parts[-3]
        return parts[-2]
    return parts[-1]

def extract_issue_number(url):
    """Извлекает номер задачи из URL (например, .../issues/17806 -> 17806)."""
    match = re.search(r'/issues/(\d+)', url)
    if match:
        return match.group(1)
    return None

# --- 3. Парсинг текста ---

def parse_event_text(text):
    print("[DEBUG] Parsing text...")
    event_data = {
        "title": "Без названия",
        "start": None,
        "end": None,
        "url": "",
        "notes": text,
        "location": ""
    }

    # 1. Организатор (Organizer, From)
    organizer_email = ""
    org_match = re.search(r'(?:Organizer|From):\s*\n?(.+)', text, re.IGNORECASE)
    if org_match:
        org_text = org_match.group(1).strip()
        email_match = re.search(r'<([^>]+)>', org_text)
        if email_match:
            organizer_email = email_match.group(1)
        else:
            email_match = re.search(r'([^\s]+@[^\s]+)', org_text)
            if email_match:
                organizer_email = email_match.group(1)

    organizer_domain = get_organizer_domain(organizer_email)
    if organizer_domain:
        print(f"[DEBUG] Organizer domain: {organizer_domain}")

    # 2. Заголовок (Title, 件名, Тема)
    title_match = re.search(r'(?:Title|件名|Тема):\s*(.+)', text, re.IGNORECASE)
    original_title = ""
    if title_match:
        original_title = title_match.group(1).strip()

    # 3. Формируем заголовок
    issue_number = None
    if original_title.startswith('http'):
        issue_number = extract_issue_number(original_title)

    if issue_number and organizer_domain:
        event_data["title"] = f"{organizer_domain}: #{issue_number}"
    elif issue_number:
        event_data["title"] = f"#{issue_number}"
    elif original_title:
        event_data["title"] = original_title
    else:
        # Если нет заголовка, ищем URL в первой строке
        first_line = text.split('\n')[0].strip()
        url_in_line = re.search(r'(https?://[^\s]+)', first_line)
        if url_in_line:
            issue_number = extract_issue_number(url_in_line.group(1))
            if issue_number and organizer_domain:
                event_data["title"] = f"{organizer_domain}: #{issue_number}"
            elif issue_number:
                event_data["title"] = f"#{issue_number}"
            else:
                event_data["title"] = first_line[:80]
        else:
            event_data["title"] = "Встреча"

    print(f"[DEBUG] Generated title: {event_data['title']}")

    # 4. Location
    loc_match = re.search(r'Location:\s*(.+)', text, re.IGNORECASE)
    if loc_match:
        loc = loc_match.group(1).strip()
        event_data["location"] = loc
        if loc.startswith('http'):
            event_data["url"] = loc

    # 5. URL (если не нашли в Location)
    if not event_data["url"]:
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            event_data["url"] = url_match.group(1)

    # 6. Дата и время (When, Когда)
    when_match = re.search(r'(?:When|Когда):\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if when_match:
        when_str = when_match.group(1).strip()
        print(f"[DEBUG] Found date field: {when_str}")
        parse_when_string(when_str, event_data)
    else:
        # Если нет When/Когда, ищем Date/Дата
        date_match = re.search(r'(?:Date|Дата):\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1).strip()
            print(f"[DEBUG] Found 'Date:' string: {date_str}")
            try:
                start_dt = dateparser.parse(date_str, languages=['ru', 'en'])
                if start_dt:
                    event_data["start"] = start_dt
                    event_data["end"] = start_dt + timedelta(hours=1)
                    print(f"[DEBUG] Using 'Date:' as start: {start_dt}")
            except Exception as e:
                print(f"[DEBUG] Dateparse error (Date): {e}")
        else:
            print("[DEBUG] No 'When/Когда' or 'Date/Дата' string found.")

    return event_data

def parse_when_string(when_str, event_data):
    """Парсит строку When: и заполняет event_data."""
    parts = re.split(r'[–-]', when_str)
    if len(parts) >= 2:
        start_part = parts[0].strip()
        end_part = parts[1].strip()

        try:
            start_dt = dateparser.parse(start_part, languages=['ru', 'en'])
            if start_dt:
                event_data["start"] = start_dt
                print(f"[DEBUG] Parsed start: {start_dt}")
        except Exception as e:
            print(f"[DEBUG] Dateparse error (start): {e}")

        if event_data["start"]:
            time_only_match = re.match(r'^\d{1,2}:\d{2}$', end_part)
            if time_only_match:
                date_str = event_data["start"].strftime("%Y-%m-%d")
                end_full_str = f"{date_str} {end_part}"
                try:
                    end_dt = dateparser.parse(end_full_str, languages=['ru', 'en'])
                    if end_dt:
                        event_data["end"] = end_dt
                        print(f"[DEBUG] Parsed end: {end_dt}")
                except Exception as e:
                    print(f"[DEBUG] Dateparse error (end time): {e}")
            else:
                try:
                    end_dt = dateparser.parse(end_part, languages=['ru', 'en'])
                    if end_dt:
                        event_data["end"] = end_dt
                        print(f"[DEBUG] Parsed end: {end_dt}")
                except Exception as e:
                    print(f"[DEBUG] Dateparse error (end): {e}")

# --- 4. Экранирование и диалог ---

def escape_applescript_string(s):
    """Надёжное экранирование для AppleScript."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')

def show_confirmation_dialog(event_data):
    print("[DEBUG] Showing confirmation dialog...")
    if not event_data["start"]:
        print("[ERROR] Cannot show dialog: no start date parsed.")
        return False

    start_str = event_data["start"].strftime("%A, %B %d, %Y at %H:%M")
    end_str = event_data["end"].strftime("%H:%M") if event_data["end"] else "?"

    safe_start = escape_applescript_string(start_str)
    safe_end = escape_applescript_string(end_str)

    if event_data["url"]:
        safe_url = escape_applescript_string(event_data["url"])
        link_line = f"🔗 {safe_url}"
    else:
        link_line = "🔗 No link"

    dialog_text = f"📅 {safe_start} — {safe_end}\\n{link_line}"
    default_answer = escape_applescript_string(event_data["title"])

    script = f'''
    tell application "System Events"
        activate
        set dialogResult to display dialog "{dialog_text}" default answer "{default_answer}" buttons {{"Cancel", "Add to Calendar"}} default button "Add to Calendar" with title "Confirm Event" with icon note
        return {{button returned of dialogResult, text returned of dialogResult}}
    end tell
    '''

    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        print(f"[DEBUG] Dialog stdout: '{result.stdout.strip()}'")

        if "Add to Calendar" in result.stdout:
            parts = result.stdout.strip().split(", ", 1)
            if len(parts) == 2:
                event_data["title"] = parts[1].strip()
            return True
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] Dialog timed out.")
        return False

# --- 5. Создание события ---

def create_event_in_calendar(event_data):
    print("[DEBUG] Creating event in calendar...")
    store = EventKit.EKEventStore.alloc().init()

    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    if status == EventKit.EKAuthorizationStatusNotDetermined:
        print("[DEBUG] Requesting calendar access...")
        granted = [False]
        done = threading.Event()
        def completion(g, err):
            granted[0] = g
            done.set()
        store.requestFullAccessToEventsWithCompletion_(completion)
        done.wait(timeout=10)
        if not granted[0]:
            print("[ERROR] Access denied.")
            return False

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setTitle_(event_data["title"])
    event.setNotes_(event_data["notes"])

    if event_data["url"]:
        event.setURL_(NSURL.URLWithString_(event_data["url"]))

    if event_data["location"]:
        event.setLocation_(event_data["location"])

    if event_data["start"] and event_data["end"]:
        start_ts = event_data["start"].timestamp()
        end_ts = event_data["end"].timestamp()
        event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(start_ts))
        event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(end_ts))
    else:
        print("[ERROR] Missing start or end date.")
        return False

    default_calendar = store.defaultCalendarForNewEvents()
    event.setCalendar_(default_calendar)

    success, error = store.saveEvent_span_commit_error_(event, EventKit.EKSpanThisEvent, True, None)
    if success:
        print(f"[DEBUG] Event '{event_data['title']}' created successfully.")
        subprocess.Popen(["open", "-a", "Calendar"])
        return True
    else:
        print(f"[ERROR] Failed to create event: {error}")
        return False

# --- 6. Основная функция ---

def add_event_from_clipboard():
    print("[DEBUG] add_event_from_clipboard called.")
    text = get_clipboard_text()
    if not text:
        print("[ERROR] Clipboard is empty.")
        return

    event_data = parse_event_text(text)

    if not show_confirmation_dialog(event_data):
        print("[DEBUG] User cancelled or dialog failed.")
        return

    if create_event_in_calendar(event_data):
        print("[DEBUG] Event added successfully.")
    else:
        print("[ERROR] Failed to add event.")