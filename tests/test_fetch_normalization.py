# tests/test_fetch_normalization.py
"""Проверяет, что _fetch_events нормализует url/location при чтении.

Использует фейковый EventKit-объект, чтобы не зависеть от реального календаря.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class FakeURL:
    def __init__(self, s):
        self._s = s

    def absoluteString(self):
        return self._s


class FakeNSDate:
    def __init__(self, dt):
        self._t = dt.timestamp()

    def timeIntervalSince1970(self):
        return self._t


class FakeCal:
    def title(self):
        return "Work"


class FakeEvent:
    def __init__(self, title, url="", location="", notes="", start=None, end=None):
        self._title = title
        self._url = FakeURL(url) if url else None
        self._loc = location
        self._notes = notes
        self._start = start or datetime.now()
        self._end = end or (self._start + timedelta(hours=1))

    def title(self):
        return self._title

    def startDate(self):
        return FakeNSDate(self._start)

    def endDate(self):
        return FakeNSDate(self._end)

    def URL(self):
        return self._url

    def location(self):
        return self._loc

    def notes(self):
        return self._notes

    def eventIdentifier(self):
        return "fake-1"

    def calendar(self):
        return FakeCal()


class FakeStore:
    def __init__(self, events):
        self._events = events

    def calendarsForEntityType_(self, _):
        return [FakeCal()]

    def predicateForEventsWithStartDate_endDate_calendars_(self, s, e, c):
        return None

    def eventsMatchingPredicate_(self, _):
        return self._events


def _fetch_one(url="", location="", notes="", title="Test"):
    from calendar_service import _fetch_events
    ev = FakeEvent(title, url=url, location=location, notes=notes)
    now = datetime.now()
    res = _fetch_events(FakeStore([ev]), now - timedelta(minutes=5), now + timedelta(hours=2))
    assert len(res) == 1, f"expected 1 event, got {len(res)}"
    return res[0]


def test_swapped_meeting_tracker():
    """URL=meeting, Location=tracker → свапнуть в tracker/meeting."""
    ev = _fetch_one(
        url="https://mts-link.ru/j/1",
        location="https://support.igtel.ru/issues/1",
    )
    assert "support.igtel.ru" in ev["url"]
    assert "mts-link.ru" in ev["location"]


def test_correct_tracker_meeting_not_swapped():
    ev = _fetch_one(
        url="https://support.igtel.ru/issues/1",
        location="https://mts-link.ru/j/1",
    )
    assert "support.igtel.ru" in ev["url"]
    assert "mts-link.ru" in ev["location"]


def test_non_url_location_kept():
    """Location = физический адрес (не URL) — не трогаем."""
    ev = _fetch_one(
        url="https://support.igtel.ru/issues/1",
        location="Room 5",
    )
    assert "support.igtel.ru" in ev["url"]
    assert ev["location"] == "Room 5"


def test_empty_url_recovered_from_title():
    """Title = '#N', tracker_base_url задан → url восстановлен."""
    from config import CONFIG
    old = CONFIG.get("tracker_base_url")
    try:
        CONFIG["tracker_base_url"] = "https://support.igtel.ru/issues/"
        ev = _fetch_one(title="MTS. #17702", url="", location="")
        assert ev["url"] == "https://support.igtel.ru/issues/17702"
    finally:
        CONFIG["tracker_base_url"] = old


def test_only_meeting_no_tracker():
    ev = _fetch_one(url="", location="https://mts-link.ru/j/1")
    assert ev["url"] == ""
    assert "mts-link.ru" in ev["location"]


def test_title_normalized():
    from config import CONFIG
    old = CONFIG.get("custom_tracker_domains")
    try:
        CONFIG["custom_tracker_domains"] = []
        ev = _fetch_one(title="MTS. https://support.example.com/issues/17702")
        assert ev["title"] == "MTS. #17702"
    finally:
        CONFIG["custom_tracker_domains"] = old


def test_notes_tracker_fills_url():
    """url пуст, location пуст, но в notes есть /issues/N — попадёт в url."""
    from config import CONFIG
    old = CONFIG.get("custom_tracker_domains")
    try:
        CONFIG["custom_tracker_domains"] = []
        ev = _fetch_one(
            title="Созвон",
            notes="Трекер: https://jira.example.com/issues/42",
        )
        assert "jira.example.com" in ev["url"]
    finally:
        CONFIG["custom_tracker_domains"] = old


if __name__ == "__main__":
    tests = [
        test_swapped_meeting_tracker,
        test_correct_tracker_meeting_not_swapped,
        test_non_url_location_kept,
        test_empty_url_recovered_from_title,
        test_only_meeting_no_tracker,
        test_title_normalized,
        test_notes_tracker_fills_url,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ {t.__name__}: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"{failed} test(s) failed")
        sys.exit(1)
    print(f"All {len(tests)} tests passed")
