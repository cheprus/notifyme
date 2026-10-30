# tests/test_smoke.py
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_normalize_title():
    from calendar_service import _normalize_title
    assert _normalize_title("MTS. https://support.example.com/issues/17702") == "MTS. #17702"
    assert _normalize_title("https://jira.example.com/issues/42") == "#42"
    assert _normalize_title("Ретро https://example.com/issues/555") == "Ретро #555"
    assert _normalize_title("MTS. #17702") == "MTS. #17702"
    assert _normalize_title("Созвон") == "Созвон"
    assert _normalize_title("") == ""
    assert _normalize_title(None) is None


def test_classify_url():
    from calendar_service import classify_url
    assert classify_url("https://zoom.us/j/123") == "meeting"
    assert classify_url("https://meet.google.com/abc") == "meeting"
    assert classify_url("https://teams.microsoft.com/l/meetup-join/...") == "meeting"
    assert classify_url("https://jira.example.com/browse/PROJ-1") == "tracker"
    assert classify_url("https://github.com/org/repo/pull/1") == "tracker"
    assert classify_url("https://confluence.example.com/wiki/spaces/X") == "tracker"
    assert classify_url("https://unknown.example.com/foo") == "unknown"
    assert classify_url("") == "unknown"


def test_format_time_delta_compact():
    from time_utils import format_time_delta_compact
    assert format_time_delta_compact(0) == "0m"
    assert format_time_delta_compact(5) == "5m"
    assert format_time_delta_compact(65) == "1h5m"
    assert format_time_delta_compact(120) == "2h"
    assert format_time_delta_compact(60 * 24 + 60 * 3) == "1d3h"
    assert format_time_delta_compact(-5) == "5m"


def test_format_countdown():
    from time_utils import format_countdown
    msk = ZoneInfo("Europe/Moscow")
    now = datetime(2026, 10, 30, 10, 0, tzinfo=msk)

    start = now + timedelta(minutes=45)
    end = start + timedelta(hours=1)
    assert format_countdown(start, end, now) == "45m"

    start_ongoing = now - timedelta(minutes=5)
    assert format_countdown(start_ongoing, now + timedelta(minutes=10), now) == "▶5m"

    start_past = now - timedelta(hours=2)
    end_past = now - timedelta(hours=1)
    assert format_countdown(start_past, end_past, now) == "−2h"

    assert format_countdown(None, None, now) == ""


def test_is_work_event():
    from color_utils import is_work_event
    assert is_work_event({"calendar_title": "Рабочий"}) is True
    assert is_work_event({"calendar_title": "Работа - встречи"}) is True
    assert is_work_event({"calendar_title": "MTS"}) is True
    assert is_work_event({"calendar_title": "Work"}) is True
    assert is_work_event({"calendar_title": "Дом"}) is False
    assert is_work_event({"calendar_title": "Home"}) is False
    assert is_work_event({"calendar_title": "Личный"}) is False
    # по title события
    assert is_work_event({"calendar_title": "Home", "title": "Рабочая встреча"}) is True


def test_get_calendar_color_stable():
    from color_utils import get_calendar_color

    ev_work = {"calendar_title": "Рабочий"}
    c1 = get_calendar_color(ev_work)
    c2 = get_calendar_color(ev_work)
    assert c1.redComponent() == c2.redComponent()
    assert c1.greenComponent() == c2.greenComponent()
    assert c1.blueComponent() == c2.blueComponent()

    ev_home = {"calendar_title": "Дом"}
    assert get_calendar_color(ev_work).alphaComponent() == 1.0
    assert abs(get_calendar_color(ev_home).alphaComponent() - 0.55) < 0.01


if __name__ == "__main__":
    tests = [
        test_normalize_title,
        test_classify_url,
        test_format_time_delta_compact,
        test_format_countdown,
        test_is_work_event,
        test_get_calendar_color_stable,
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
