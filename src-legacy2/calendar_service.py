# src/calendar_service.py
import re
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from typing import Any

try:
    import EventKit
    from Foundation import NSDate
except ImportError:
    print("Please install: pip install pyobjc-framework-EventKit")
    sys.exit(1)

from config import CONFIG

REPORT_GRACE_MINUTES = 60
DEBUG_LOG = "/tmp/notifyme_debug.log"


def _target_calendar_name():
    return CONFIG.get("target_calendar_name", "").strip()


def _log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


_ANY_ISSUE_URL_RE = re.compile(r"https?://[^\s]*?/issues/(\d+)", re.IGNORECASE)
_HASH_ISSUE_RE = re.compile(r"(?:^|\s)#(\d+)(?=\s|$|[,.;:!?])")


def _normalize_title(title):
    if not title:
        return title
    t = title.strip()
    t = _ANY_ISSUE_URL_RE.sub(lambda m: f"#{m.group(1)}", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _recover_tracker_url(title, notes):
    haystack = " ".join(filter(None, [title or "", notes or ""]))

    for domain in CONFIG.get("custom_tracker_domains", []) or []:
        if not domain:
            continue
        m = re.search(r"https?://[^\s]*?" + re.escape(domain) + r"[^\s]*", haystack, re.IGNORECASE)
        if m:
            return m.group(0)

    m = _ANY_ISSUE_URL_RE.search(haystack)
    if m:
        return m.group(0)

    base = CONFIG.get("tracker_base_url", "").strip()
    if base:
        m = _HASH_ISSUE_RE.search(haystack)
        if m:
            if not base.endswith("/"):
                base += "/"
            return f"{base}{m.group(1)}"

    return ""


def request_calendar_access():
    store = EventKit.EKEventStore.alloc().init()
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    _log(f"Calendar authorization status: {status}")

    if status == EventKit.EKAuthorizationStatusAuthorized or status == EventKit.EKAuthorizationStatusFullAccess:
        return store

    if status == EventKit.EKAuthorizationStatusNotDetermined:
        granted = [False]
        done = threading.Event()

        def completion(g, err):
            granted[0] = g
            _log(f"Calendar access completion: granted={g}, err={err}")
            done.set()

        store.requestFullAccessToEventsWithCompletion_(completion)
        done.wait(timeout=10)

    return store


def list_calendars(store) -> list[dict[str, Any]]:
    # mypy: result: list[dict[str, Any]]
    result: list[dict[str, Any]] = []
    if store is None:
        return result
    try:
        cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        for cal in cals:
            try:
                info: dict[str, Any] = {
                    "title": cal.title(),
                    "type": cal.type(),
                    "allows_modifications": cal.allowsContentModifications(),
                    "calendar_identifier": cal.calendarIdentifier(),
                }
                result.append(info)
            except Exception as e:
                result.append({"error": str(e)})
    except Exception as e:
        _log(f"list_calendars error: {e}")
    return result


def get_default_calendar_name(store):
    if store is None:
        return ""
    try:
        cal = store.defaultCalendarForNewEvents()
        if cal is not None:
            return cal.title() or ""
    except Exception as e:
        _log(f"defaultCalendarForNewEvents error: {e}")
    return ""


def _calendar_exists(store, name):
    if not name or store is None:
        return False
    try:
        for cal in store.calendarsForEntityType_(EventKit.EKEntityTypeEvent):
            if cal.title() == name:
                return True
    except Exception as e:
        _log(f"_calendar_exists error: {e}")
    return False


def _fetch_events(store, start_dt, end_dt):
    def to_nsdate(dt):
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    try:
        calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            to_nsdate(start_dt), to_nsdate(end_dt), calendars
        )
        events = store.eventsMatchingPredicate_(predicate)
    except Exception as e:
        _log(f"Error fetching events: {e}")
        return []

    result = []
    if events:
        for event in events:
            raw_title = event.title() or "Untitled"
            title = _normalize_title(raw_title)

            start_date = event.startDate()
            end_date = event.endDate()
            if start_date is None or end_date is None:
                continue
            start = datetime.fromtimestamp(start_date.timeIntervalSince1970())
            end = datetime.fromtimestamp(end_date.timeIntervalSince1970())
            url = event.URL()
            url_str = url.absoluteString() if url else ""
            location = event.location() or ""
            notes = event.notes() or ""
            unique_id = f"{event.eventIdentifier()}_{start.isoformat()}"

            cal = event.calendar()
            cal_title = cal.title() if cal else ""

            if not url_str:
                url_str = _recover_tracker_url(raw_title, notes)

            result.append({
                "title": title,
                "start": start,
                "end": end,
                "url": url_str,
                "location": location,
                "notes": notes,
                "id": unique_id,
                "calendar_title": cal_title,
            })
    return result


def get_upcoming_events(store):
    if store is None:
        return []
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    events = _fetch_events(store, start_of_day, end_of_day)

    filtered = []
    for ev in events:
        if now <= ev["end"] + timedelta(minutes=REPORT_GRACE_MINUTES):
            filtered.append(ev)
    filtered.sort(key=lambda e: e["start"])
    return filtered


def get_week_events(store):
    if store is None:
        return []
    now = datetime.now()
    start_of_tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_tomorrow + timedelta(days=7)
    return _fetch_events(store, start_of_tomorrow, end_of_week)


def get_dialog_message(start_dt, now):
    delta_minutes = (start_dt - now).total_seconds() / 60.0
    if delta_minutes > 0:
        if delta_minutes < 1:
            return "Event starting in less than a minute"
        return f"Event starting in {int(delta_minutes)} minutes"
    else:
        minutes_ago = int(abs(delta_minutes))
        if minutes_ago == 0:
            return "Event just started"
        return f"Event started {minutes_ago} minutes ago"


# ---------- Классификация ссылок ----------

_TRACKER_PATTERNS = [
    r"support\.igtel\.ru",
    r"jira",
    r"confluence",
    r"atlassian\.net",
    r"github\.com",
    r"gitlab",
    r"bitbucket",
    r"youtrack",
    r"redmine",
    r"trello\.com",
    r"asana\.com",
    r"notion\.so",
    r"miro\.com",
    r"/issues/",
    r"/browse/",
    r"/tickets?/",
    r"/tasks?/",
    r"/wiki/",
]

_MEETING_PATTERNS = [
    r"\bmts-link\.ru",
    r"\bzoom\.us",
    r"\bmeet\.google\.com",
    r"\bteams\.microsoft\.com",
    r"\bwebex\.com",
    r"\bwhereby\.com",
    r"\bjitsi",
    r"\bmeet\.jivo\.ru",
    r"/j/\d+",
    r"/session/\d+",
    r"/meet/",
    r"/conference/",
]


def _custom_patterns(key):
    result = []
    for d in CONFIG.get(key, []) or []:
        d = (d or "").strip()
        if not d:
            continue
        result.append(re.escape(d))
    return result


def classify_url(url):
    if not url:
        return "unknown"
    u = url.lower().strip()

    for pat in _custom_patterns("custom_meeting_domains"):
        if re.search(pat, u):
            return "meeting"

    for pat in _custom_patterns("custom_tracker_domains"):
        if re.search(pat, u):
            return "tracker"

    for pat in _MEETING_PATTERNS:
        if re.search(pat, u):
            return "meeting"
    for pat in _TRACKER_PATTERNS:
        if re.search(pat, u):
            return "tracker"
    return "unknown"


def split_links(tracker_url, meeting_url, notes):
    url_field = (tracker_url or "").strip()
    location_field = (meeting_url or "").strip()

    if url_field and location_field:
        url_kind = classify_url(url_field)
        loc_kind = classify_url(location_field)
        if url_kind == "meeting" and loc_kind == "tracker":
            return location_field, url_field
        return url_field, location_field

    if notes:
        found = re.findall(r'https?://[^\s<>"\']+', notes)
        for link in found:
            kind = classify_url(link)
            if kind == "tracker" and not url_field:
                url_field = link
            elif kind == "meeting" and not location_field:
                location_field = link

    if url_field and not location_field:
        kind = classify_url(url_field)
        if kind == "meeting":
            location_field, url_field = url_field, ""
    if location_field and not url_field:
        kind = classify_url(location_field)
        if kind == "tracker":
            url_field, location_field = location_field, ""

    return url_field, location_field


# ---------- AppleScript helpers ----------

def _escape_applescript(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def _run_osascript(script, timeout=10):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        _log(f"osascript rc={r.returncode}")
        if r.stdout.strip():
            _log(f"osascript stdout: {r.stdout.strip()!r}")
        if r.stderr.strip():
            _log(f"osascript stderr: {r.stderr.strip()!r}")
        return r
    except subprocess.TimeoutExpired:
        _log("osascript TIMEOUT")
        return None
    except Exception as e:
        _log(f"osascript exception: {e}")
        return None


def _try_create_event(title, start_dt, end_dt, notes, tracker_url, meeting_url, target_name, store):
    sy, sm, sd = start_dt.year, start_dt.month, start_dt.day
    sh, smin = start_dt.hour, start_dt.minute
    ey, em, ed = end_dt.year, end_dt.month, end_dt.day
    eh, emin = end_dt.hour, end_dt.minute

    safe_title = _escape_applescript(title)
    safe_notes = _escape_applescript(notes)
    safe_url = _escape_applescript(tracker_url)
    safe_location = _escape_applescript(meeting_url)
    safe_cal = _escape_applescript(target_name)

    if safe_cal:
        cal_lookup = f'''
        try
            set targetCal to calendar "{safe_cal}"
        on error
            return "ERROR: calendar not found: {safe_cal}"
        end try
        '''
    else:
        cal_lookup = """
        set targetCal to missing value
        try
            repeat with c in calendars
                if writable of c is true then
                    set targetCal to c
                    exit repeat
                end if
            end repeat
        end try
        if targetCal is missing value then
            return "ERROR: no writable calendar found"
        end if
        """

    script_create = f'''
    tell application "Calendar"
        set startDate to current date
        set year of startDate to {sy}
        set month of startDate to {sm}
        set day of startDate to {sd}
        set hours of startDate to {sh}
        set minutes of startDate to {smin}
        set seconds of startDate to 0

        set endDate to current date
        set year of endDate to {ey}
        set month of endDate to {em}
        set day of endDate to {ed}
        set hours of endDate to {eh}
        set minutes of endDate to {emin}
        set seconds of endDate to 0

        {cal_lookup}
        tell targetCal
            set newEvent to make new event with properties {{summary:"{safe_title}", start date:startDate, end date:endDate, description:"{safe_notes}", url:"{safe_url}", location:"{safe_location}"}}
            return (summary of newEvent) & " | " & ((start date of newEvent) as string) & " | " & ((end date of newEvent) as string) & " | url=" & (url of newEvent) & " | loc=" & (location of newEvent)
        end tell
    end tell
    '''
    r = _run_osascript(script_create)
    if r is None:
        return False, "osascript timeout"
    if r.returncode != 0:
        return False, r.stderr.strip() or "AppleScript create error"

    returned = r.stdout.strip()
    _log(f"CREATE RETURNED: {returned!r}")
    if not returned:
        return False, "AppleScript returned empty"
    if returned.startswith("ERROR: calendar not found"):
        return False, f"calendar not found: {target_name}"
    if returned.startswith("ERROR: no writable calendar"):
        return False, "no writable calendar found"

    verify_start = start_dt - timedelta(seconds=30)
    verify_end = end_dt + timedelta(seconds=30)
    try:
        events = _fetch_events(store, verify_start, verify_end)
        for ev in events:
            if ev["title"] == title and abs((ev["start"] - start_dt).total_seconds()) < 60:
                return True, None
    except Exception as e:
        _log(f"EventKit verify error: {e}")

    return True, None


def create_event_via_applescript(title, start_dt, end_dt, notes, url, video_url=""):
    _log("=" * 60)
    _log("CREATE EVENT START")

    tracker_url, meeting_url = split_links(url, video_url, notes)

    if not tracker_url:
        recovered = _recover_tracker_url(title, notes)
        if recovered:
            tracker_url = recovered
            _log(f"Recovered tracker URL: {tracker_url!r}")

    normalized_title = _normalize_title(title)

    _log(f"Title (raw): {title!r}")
    _log(f"Title (normalized): {normalized_title!r}")
    _log(f"Start: {start_dt}")
    _log(f"End:   {end_dt}")
    _log(f"Tracker URL (→ event.url): {tracker_url!r}")
    _log(f"Meeting URL (→ event.location): {meeting_url!r}")

    store = request_calendar_access()

    candidates = []
    configured = _target_calendar_name()
    if configured and _calendar_exists(store, configured):
        candidates.append((configured, "config"))
    elif configured:
        _log(f"Configured calendar {configured!r} not found — trying default")
    default_name = get_default_calendar_name(store)
    if default_name:
        candidates.append((default_name, "default"))
    candidates.append(("", "writable-fallback"))

    last_error = "Unknown error"
    for target_name, source in candidates:
        _log(f"Trying target calendar: {target_name!r} (source={source})")
        ok, err = _try_create_event(
            title=normalized_title,
            start_dt=start_dt,
            end_dt=end_dt,
            notes=notes,
            tracker_url=tracker_url,
            meeting_url=meeting_url,
            target_name=target_name,
            store=store,
        )
        if ok:
            _log(f"✅ Event created in calendar: {target_name!r} (source={source})")
            return True, None
        last_error = err
        _log(f"⚠️ Failed to create in {target_name!r}: {err}")

    return False, last_error
