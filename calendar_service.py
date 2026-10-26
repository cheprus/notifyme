# calendar_service.py
import sys
import threading
from datetime import datetime, timedelta

try:
    import EventKit
    from Foundation import NSDate
except ImportError:
    print("Please install: pip install pyobjc-framework-EventKit")
    sys.exit(1)

REPORT_GRACE_MINUTES = 60

def request_calendar_access():
    """Запрашивает доступ к календарю."""
    store = EventKit.EKEventStore.alloc().init()
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    print(f"[DEBUG] Calendar status: {status}")
    
    if status == EventKit.EKAuthorizationStatusAuthorized or status == EventKit.EKAuthorizationStatusFullAccess:
        print("[DEBUG] Calendar access granted.")
        return store
        
    if status == EventKit.EKAuthorizationStatusNotDetermined:
        print("[DEBUG] Requesting calendar access...")
        granted = [False]
        done = threading.Event()
        def completion(g, err):
            granted[0] = g
            done.set()
        store.requestFullAccessToEventsWithCompletion_(completion)
        done.wait(timeout=10)
        if granted[0]:
            print("[DEBUG] Calendar access granted by user.")
        else:
            print("[DEBUG] Calendar access denied by user.")
    else:
        print("[DEBUG] Calendar access denied or restricted.")
        
    return store

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
        print(f"Error fetching events: {e}")
        return []
    
    result = []
    if events:
        for event in events:
            title = event.title() or "Untitled"
            start_date = event.startDate()
            end_date = event.endDate()
            if start_date is None or end_date is None:
                continue
            start = datetime.fromtimestamp(start_date.timeIntervalSince1970())
            end = datetime.fromtimestamp(end_date.timeIntervalSince1970())
            url = event.URL()
            url_str = url.absoluteString() if url else ""
            unique_id = f"{event.eventIdentifier()}_{start.isoformat()}"
            result.append({
                "title": title,
                "start": start,
                "end": end,
                "url": url_str,
                "id": unique_id
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
