# tests/test_logic.py
import os
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ============================================================
# calendar_service: normalize_title, recover_tracker_url, split_links
# ============================================================

def test_normalize_title():
    from calendar_service import _normalize_title
    assert _normalize_title("MTS. https://support.example.com/issues/17702") == "MTS. #17702"
    assert _normalize_title("https://jira.example.com/issues/42") == "#42"
    assert _normalize_title("Ретро https://example.com/issues/555") == "Ретро #555"
    assert _normalize_title("MTS. #17702") == "MTS. #17702"
    assert _normalize_title("Созвон") == "Созвон"
    assert _normalize_title("") == ""
    assert _normalize_title(None) is None
    assert _normalize_title("  Двойные   пробелы  ") == "Двойные пробелы"


def test_recover_tracker_url():
    from calendar_service import _recover_tracker_url
    r = _recover_tracker_url("MTS. https://support.igtel.ru/issues/17702", "")
    assert r == "https://support.igtel.ru/issues/17702"

    r = _recover_tracker_url("Ретро https://jira.example.com/issues/42", "")
    assert r == "https://jira.example.com/issues/42"

    r = _recover_tracker_url("MTS. #17702", "")
    assert r == "https://support.igtel.ru/issues/17702"

    assert _recover_tracker_url("Созвон", "") == ""
    assert _recover_tracker_url("", "") == ""

    r = _recover_tracker_url("Созвон", "Описание https://support.igtel.ru/issues/999")
    assert r == "https://support.igtel.ru/issues/999"


def test_classify_url():
    from calendar_service import classify_url
    cases = [
        ("https://zoom.us/j/123", "meeting"),
        ("https://meet.google.com/abc", "meeting"),
        ("https://teams.microsoft.com/l/meetup-join/...", "meeting"),
        ("https://webex.com/meet/...", "meeting"),
        ("https://whereby.com/room", "meeting"),
        ("https://jitsi.example.com/room", "meeting"),
        ("https://mts-link.ru/j/123/456/session/789", "meeting"),
        ("https://jira.example.com/browse/PROJ-1", "tracker"),
        ("https://github.com/org/repo/pull/1", "tracker"),
        ("https://confluence.example.com/wiki/spaces/X", "tracker"),
        ("https://support.igtel.ru/issues/17702", "tracker"),
        ("https://unknown.example.com/foo", "unknown"),
        ("", "unknown"),
    ]
    for url, expected in cases:
        assert classify_url(url) == expected, f"{url} -> {classify_url(url)}, expected {expected}"


def test_split_links():
    from calendar_service import split_links
    tracker, meeting = split_links(
        "https://support.igtel.ru/issues/1",
        "https://mts-link.ru/j/1",
        "",
    )
    assert "support.igtel.ru" in tracker
    assert "mts-link.ru" in meeting

    tracker, meeting = split_links(
        "https://mts-link.ru/j/1",
        "https://support.igtel.ru/issues/1",
        "",
    )
    assert "support.igtel.ru" in tracker
    assert "mts-link.ru" in meeting

    tracker, meeting = split_links("", "", "Описание https://support.igtel.ru/issues/9")
    assert "support.igtel.ru" in tracker
    assert meeting == ""


# ============================================================
# time_utils
# ============================================================

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


def test_format_event_datetime():
    from config import CONFIG
    from time_utils import format_event_datetime

    old = CONFIG.get("display_timezone")
    CONFIG["display_timezone"] = "Europe/Moscow"
    try:
        msk = ZoneInfo("Europe/Moscow")
        now = datetime(2026, 10, 30, 10, 0, tzinfo=msk)

        start = now.replace(hour=15, minute=30)
        s = format_event_datetime(start, now)
        assert "15:30" in s, f"got {s!r}"

        start = now + timedelta(days=1)
        s = format_event_datetime(start, now)
        assert "31" in s, f"got {s!r}"

        assert format_event_datetime(None, now) == ""
    finally:
        CONFIG["display_timezone"] = old


def test_format_event_datetime_for_copy():
    from config import CONFIG
    from time_utils import format_event_datetime_for_copy

    old_display = CONFIG.get("display_timezone")
    old_copy = CONFIG.get("copy_timezone")
    CONFIG["display_timezone"] = "Europe/Moscow"
    CONFIG["copy_timezone"] = "Europe/Moscow"
    try:
        msk = ZoneInfo("Europe/Moscow")
        now = datetime(2026, 10, 30, 10, 0, tzinfo=msk)
        start = datetime(2026, 10, 30, 15, 30, tzinfo=msk)
        s = format_event_datetime_for_copy(start, now)
        assert "МСК" in s, f"got {s!r}"
        assert "15:30" in s, f"got {s!r}"
    finally:
        CONFIG["display_timezone"] = old_display
        CONFIG["copy_timezone"] = old_copy


# ============================================================
# color_utils
# ============================================================

def test_is_work_event():
    from color_utils import is_work_event
    assert is_work_event({"calendar_title": "Рабочий"}) is True
    assert is_work_event({"calendar_title": "Работа - встречи"}) is True
    assert is_work_event({"calendar_title": "MTS"}) is True
    assert is_work_event({"calendar_title": "Work"}) is True
    assert is_work_event({"calendar_title": "Дом"}) is False
    assert is_work_event({"calendar_title": "Home"}) is False
    assert is_work_event({"calendar_title": "Личный"}) is False
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


# ============================================================
# alarm_utils
# ============================================================

def test_compute_alarm_lifetime():
    from datetime import datetime as dt

    from alarm_utils import _compute_alarm_lifetime
    from config import CONFIG

    old = CONFIG.get("auto_close_minutes")
    CONFIG["auto_close_minutes"] = 15
    try:
        # Встреча 10:00–11:00, notify в 09:55.
        # deadline = max(start+3=10:03, end=11:00) = 11:00
        # seconds = 65 мин > 15 → 15 мин = 900 сек
        start = dt(2026, 10, 30, 10, 0)
        end = dt(2026, 10, 30, 11, 0)
        now = dt(2026, 10, 30, 9, 55)
        events = [{"start": start, "end": end}]
        lifetime = _compute_alarm_lifetime(events, now)
        assert lifetime == 15 * 60, f"expected 900, got {lifetime}"

        # Короткая встреча 10:00–10:02, notify в 09:55.
        # deadline = max(start+3=10:03, end=10:02) = 10:03
        # seconds = 8 мин, max = 15 → 8 мин = 480 сек
        start2 = dt(2026, 10, 30, 10, 0)
        end2 = dt(2026, 10, 30, 10, 2)
        now2 = dt(2026, 10, 30, 9, 55)
        events2 = [{"start": start2, "end": end2}]
        lifetime2 = _compute_alarm_lifetime(events2, now2)
        assert lifetime2 == 8 * 60, f"expected 480, got {lifetime2}"
    finally:
        CONFIG["auto_close_minutes"] = old


def test_sound_on_off_seconds():
    from alarm_utils import _sound_off_seconds, _sound_on_seconds
    from config import CONFIG
    old_on = CONFIG.get("alarm_sound_on_seconds", 10)
    old_off = CONFIG.get("alarm_sound_off_seconds", 60)

    assert _sound_on_seconds() == max(1, int(old_on))
    assert _sound_off_seconds() == max(1, int(old_off))


# ============================================================
# status_bar
# ============================================================

def test_parse_dnd_until():
    from config import CONFIG
    from status_bar import _parse_dnd_until
    old = CONFIG.get("dnd_until")

    CONFIG["dnd_until"] = None
    assert _parse_dnd_until() is None

    CONFIG["dnd_until"] = "2026-10-30T18:00:00"
    dt = _parse_dnd_until()
    assert dt is not None
    assert dt.year == 2026
    assert dt.hour == 18

    CONFIG["dnd_until"] = "invalid"
    assert _parse_dnd_until() is None

    CONFIG["dnd_until"] = old


# ============================================================
# config
# ============================================================

def test_config_roundtrip():
    import config as cfg
    original_dir = cfg.CONFIG_DIR
    original_file = cfg.CONFIG_FILE
    with tempfile.TemporaryDirectory() as tmp:
        try:
            cfg.CONFIG_DIR = tmp
            cfg.CONFIG_FILE = os.path.join(tmp, "config.json")
            test_cfg = {
                "notify_minutes_before": 7,
                "auto_close_minutes": 20,
                "sound_file": "/System/Library/Sounds/Ping.aiff",
                "display_timezone": "UTC",
                "copy_timezone": "Europe/Moscow",
                "target_calendar_name": "Test",
                "work_calendar_hints": ["work"],
                "custom_tracker_domains": [],
                "custom_meeting_domains": [],
                "tracker_base_url": "",
                "dnd_until": None,
                "alarm_sound_on_seconds": 5,
                "alarm_sound_off_seconds": 30,
                "include_notes_in_copy": True,
            }
            cfg.save_config(test_cfg)
            loaded = cfg.load_config()
            assert loaded["notify_minutes_before"] == 7
            assert loaded["include_notes_in_copy"] is True
            assert loaded["alarm_sound_on_seconds"] == 5
        finally:
            cfg.CONFIG_DIR = original_dir
            cfg.CONFIG_FILE = original_file


# ============================================================
# runner
# ============================================================

if __name__ == "__main__":
    tests = [
        test_normalize_title,
        test_recover_tracker_url,
        test_classify_url,
        test_split_links,
        test_format_time_delta_compact,
        test_format_countdown,
        test_format_event_datetime,
        test_format_event_datetime_for_copy,
        test_is_work_event,
        test_get_calendar_color_stable,
        test_compute_alarm_lifetime,
        test_sound_on_off_seconds,
        test_parse_dnd_until,
        test_config_roundtrip,
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
