# tests/check_fetch.py
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class FakeURL:
    def __init__(self, s): self._s = s
    def absoluteString(self): return self._s

class FakeNSDate:
    def __init__(self, dt): self._t = dt.timestamp()
    def timeIntervalSince1970(self): return self._t

class FakeCal:
    def title(self): return "Work"

class FakeEvent:
    def __init__(self, title, url, location, notes="", start=None, end=None):
        self._title = title
        self._url = FakeURL(url) if url else None
        self._loc = location
        self._notes = notes
        self._start = start or datetime.now()
        self._end = end or (self._start + timedelta(hours=1))
    def title(self): return self._title
    def startDate(self): return FakeNSDate(self._start)
    def endDate(self): return FakeNSDate(self._end)
    def URL(self): return self._url
    def location(self): return self._loc
    def notes(self): return self._notes
    def eventIdentifier(self): return "fake-1"
    def calendar(self): return FakeCal()

class FakeStore:
    def __init__(self, events): self._events = events
    def calendarsForEntityType_(self, _): return [FakeCal()]
    def predicateForEventsWithStartDate_endDate_calendars_(self, s, e, c): return None
    def eventsMatchingPredicate_(self, _): return self._events


def check_case(name, url, location, expected_url, expected_loc):
    from calendar_service import _fetch_events
    ev = FakeEvent("Test", url, location, notes="")
    now = datetime.now()
    res = _fetch_events(FakeStore([ev]), now - timedelta(minutes=5), now + timedelta(hours=2))
    assert len(res) == 1, f"{name}: no events"
    got_url, got_loc = res[0]["url"], res[0]["location"]
    ok = got_url == expected_url and got_loc == expected_loc
    print(f"{'✅' if ok else '❌'} {name}")
    if not ok:
        print(f"   url     : {got_url!r} (expected {expected_url!r})")
        print(f"   location: {got_loc!r} (expected {expected_loc!r})")
    return ok


def main():
    cases = [
        # трекер в URL, meeting в Location — без свапа
        ("tracker+meeting correct",
         "https://support.igtel.ru/issues/1",
         "https://mts-link.ru/j/1",
         "https://support.igtel.ru/issues/1",
         "https://mts-link.ru/j/1"),
        # meeting в URL, трекер в Location — ДОЛЖЕН свапнуть
        ("meeting+tracker swapped",
         "https://mts-link.ru/j/1",
         "https://support.igtel.ru/issues/1",
         "https://support.igtel.ru/issues/1",
         "https://mts-link.ru/j/1"),
        # Location — физический адрес, не URL: не трогаем
        ("non-url location kept",
         "https://support.igtel.ru/issues/1",
         "Room 5",
         "https://support.igtel.ru/issues/1",
         "Room 5"),
        # пусто везде
        ("empty",
         "", "", "", ""),
    ]
    results = [check_case(*c) for c in cases]
    print()
    if all(results):
        print(f"All {len(results)} cases passed")
    else:
        print("Some cases failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
