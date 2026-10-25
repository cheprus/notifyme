# calendar_service.py
import sys
import threading
from datetime import datetime, timedelta

try:
    import EventKit
    from Foundation import NSDate
except ImportError:
    print("Пожалуйста, установите: pip install pyobjc-framework-EventKit pyobjc-framework-Cocoa")
    sys.exit(1)

REPORT_GRACE_MINUTES = 60

def request_calendar_access():
    """Запрашивает доступ к календарю у EventKit."""
    store = EventKit.EKEventStore.alloc().init()
    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
        if status == EventKit.EKAuthorizationStatusAuthorized:
            return store
        if status in (EventKit.EKAuthorizationStatusDenied, EventKit.EKAuthorizationStatusRestricted):
            print("Доступ к календарю запрещён. Проверьте Настройки → Конфиденциальность → Календарь.")
            sys.exit(1)
        
        granted = [False]
        done = threading.Event()

        def completion(g, err):
            granted[0] = g
            done.set()

        store.requestFullAccessToEventsWithCompletion_(completion)
        done.wait(timeout=10)
        if not granted[0]:
            print("Пользователь не дал доступ к календарю.")
            sys.exit(1)
    return store

def get_upcoming_events(store):
    """Получает события на сегодня, которые ещё не закончились более 60 минут назад."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    def to_nsdate(dt):
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        to_nsdate(start_of_day), to_nsdate(end_of_day), calendars
    )
    events = store.eventsMatchingPredicate_(predicate)

    result = []
    if events:
        for event in events:
            title = event.title() or "Без названия"
            start_date = event.startDate()
            end_date = event.endDate()
            if start_date is None or end_date is None:
                continue
            
            start_dt = datetime.fromtimestamp(start_date.timeIntervalSince1970())
            end_dt = datetime.fromtimestamp(end_date.timeIntervalSince1970())
            
            # Пропускаем только те события, которые закончились более 60 минут назад
            if now > end_dt + timedelta(minutes=REPORT_GRACE_MINUTES):
                continue
            
            url = event.URL()
            url_str = url.absoluteString() if url else ""
            
            # Уникальный ID, включающий время начала (чтобы изменение времени сбрасывало оповещение)
            unique_id = f"{event.eventIdentifier()}_{start_dt.isoformat()}"
            
            result.append({
                "title": title,
                "start": start_dt,
                "end": end_dt,
                "url": url_str,
                "id": unique_id
            })

    result.sort(key=lambda e: e["start"])
    return result

def get_week_events(store):
    """Получает события на 7 дней вперёд (начиная с завтрашнего дня)."""
    now = datetime.now()
    start_of_tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_tomorrow + timedelta(days=7)

    def to_nsdate(dt):
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        to_nsdate(start_of_tomorrow), to_nsdate(end_of_week), calendars
    )
    events = store.eventsMatchingPredicate_(predicate)

    result = []
    if events:
        for event in events:
            title = event.title() or "Без названия"
            start_date = event.startDate()
            end_date = event.endDate()
            if start_date is None or end_date is None:
                continue
            
            start_dt = datetime.fromtimestamp(start_date.timeIntervalSince1970())
            end_dt = datetime.fromtimestamp(end_date.timeIntervalSince1970())
            
            url = event.URL()
            url_str = url.absoluteString() if url else ""
            
            unique_id = f"{event.eventIdentifier()}_{start_dt.isoformat()}"
            
            result.append({
                "title": title,
                "start": start_dt,
                "end": end_dt,
                "url": url_str,
                "id": unique_id
            })

    result.sort(key=lambda e: e["start"])
    return result

def get_dialog_message(start_dt, now):
    """Формирует заголовок для окна."""
    delta_minutes = (start_dt - now).total_seconds() / 60.0
    if delta_minutes > 0:
        if delta_minutes < 1:
            return "Встреча начнется менее чем через минуту"
        return f"Встреча через {int(delta_minutes)} минут"
    else:
        minutes_ago = int(abs(delta_minutes))
        if minutes_ago == 0:
            return "Встреча только что началась"
        return f"Встреча началась {minutes_ago} минут назад"
