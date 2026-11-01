# tests/test_hot_reload.py
"""Проверяет, что настройки применяются без перезапуска:
модули читают CONFIG на лету, а не кэшируют значения при импорте.
"""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ============================================================
# 1. time_utils читает CONFIG на лету
# ============================================================

def test_display_timezone_hot_reload():
    from config import CONFIG
    from time_utils import to_display_tz

    old = CONFIG.get("display_timezone")
    try:
        CONFIG["display_timezone"] = "Europe/Moscow"
        utc_dt = datetime(2026, 10, 30, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert to_display_tz(utc_dt).hour == 15

        # меняем без перезапуска
        CONFIG["display_timezone"] = "Asia/Tokyo"
        assert to_display_tz(utc_dt).hour == 21
    finally:
        CONFIG["display_timezone"] = old


def test_copy_timezone_hot_reload():
    from config import CONFIG
    from time_utils import to_copy_tz

    old = CONFIG.get("copy_timezone")
    try:
        CONFIG["copy_timezone"] = "Europe/Moscow"
        utc_dt = datetime(2026, 10, 30, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert to_copy_tz(utc_dt).hour == 15

        CONFIG["copy_timezone"] = "Asia/Tokyo"
        assert to_copy_tz(utc_dt).hour == 21
    finally:
        CONFIG["copy_timezone"] = old


# ============================================================
# 2. classify читает custom_*_domains на лету
# ============================================================

def test_classify_hot_reload_tracker_domains():
    from classify import classify_url
    from config import CONFIG

    old = CONFIG.get("custom_tracker_domains")
    try:
        CONFIG["custom_tracker_domains"] = []
        # без custom-домена неизвестный URL = unknown
        assert classify_url("https://newcorp.example/board/1") == "unknown"

        # добавляем без перезапуска
        CONFIG["custom_tracker_domains"] = ["newcorp.example"]
        assert classify_url("https://newcorp.example/board/1") == "tracker"
    finally:
        CONFIG["custom_tracker_domains"] = old


def test_classify_hot_reload_meeting_domains():
    from classify import classify_url
    from config import CONFIG

    old = CONFIG.get("custom_meeting_domains")
    try:
        CONFIG["custom_meeting_domains"] = []
        assert classify_url("https://meet.newcorp.example/room/1") == "unknown"

        CONFIG["custom_meeting_domains"] = ["meet.newcorp.example"]
        assert classify_url("https://meet.newcorp.example/room/1") == "meeting"
    finally:
        CONFIG["custom_meeting_domains"] = old


# ============================================================
# 3. alarm_utils читает alarm_sound_* на лету
# ============================================================

def test_pulse_seconds_hot_reload():
    from alarm_utils import _sound_off_seconds, _sound_on_seconds
    from config import CONFIG

    old_on = CONFIG.get("alarm_sound_on_seconds")
    old_off = CONFIG.get("alarm_sound_off_seconds")
    try:
        CONFIG["alarm_sound_on_seconds"] = 7
        CONFIG["alarm_sound_off_seconds"] = 33
        assert _sound_on_seconds() == 7
        assert _sound_off_seconds() == 33

        CONFIG["alarm_sound_on_seconds"] = 20
        CONFIG["alarm_sound_off_seconds"] = 120
        assert _sound_on_seconds() == 20
        assert _sound_off_seconds() == 120
    finally:
        CONFIG["alarm_sound_on_seconds"] = old_on
        CONFIG["alarm_sound_off_seconds"] = old_off


# ============================================================
# 4. color_utils читает work_calendar_hints на лету
# ============================================================

def test_work_hints_hot_reload():
    from color_utils import is_work_event
    from config import CONFIG

    old = CONFIG.get("work_calendar_hints")
    try:
        CONFIG["work_calendar_hints"] = ["рабо"]
        assert is_work_event({"calendar_title": "Рабочий"}) is True
        assert is_work_event({"calendar_title": "Tautoki"}) is False

        CONFIG["work_calendar_hints"] = ["tautoki"]
        assert is_work_event({"calendar_title": "Tautoki"}) is True
    finally:
        CONFIG["work_calendar_hints"] = old


# ============================================================
# 5. clipboard_utils читает include_notes_in_copy на лету
# ============================================================

def test_include_notes_hot_reload():
    from clipboard_utils import format_event_for_clipboard
    from config import CONFIG

    old = CONFIG.get("include_notes_in_copy")
    try:
        now = datetime(2026, 10, 30, 10, 0, tzinfo=ZoneInfo("UTC"))
        ev = {
            "title": "X",
            "start": now,
            "notes": "важное",
        }
        CONFIG["include_notes_in_copy"] = False
        assert "📝" not in format_event_for_clipboard(ev, now)

        CONFIG["include_notes_in_copy"] = True
        assert "📝 важное" in format_event_for_clipboard(ev, now)
    finally:
        CONFIG["include_notes_in_copy"] = old


# ============================================================
# 6. status_bar._reinstall_hotkey безопасен без Accessibility
# ============================================================

def test_reinstall_hotkey_no_crash_without_ax():
    """На машине без Accessibility _reinstall_hotkey не должен падать."""
    from status_bar import StatusBarController

    class Fake:
        _hotkey_monitor = None

    try:
        StatusBarController._reinstall_hotkey_if_needed(Fake())
    except Exception as e:
        raise AssertionError(f"_reinstall_hotkey_if_needed crashed: {e}") from e


# ============================================================
# 7. notify_minutes_before читается на лету в alarm-логике
# ============================================================

def test_alarm_lifetime_hot_reload():
    from alarm_utils import _compute_alarm_lifetime
    from config import CONFIG

    old = CONFIG.get("auto_close_minutes")
    try:
        start = datetime(2026, 10, 30, 10, 0)
        end = datetime(2026, 10, 30, 11, 0)
        now = datetime(2026, 10, 30, 9, 55)
        events = [{"start": start, "end": end}]

        CONFIG["auto_close_minutes"] = 15
        assert _compute_alarm_lifetime(events, now) == 15 * 60

        CONFIG["auto_close_minutes"] = 30
        assert _compute_alarm_lifetime(events, now) == 30 * 60
    finally:
        CONFIG["auto_close_minutes"] = old


# ============================================================
# runner
# ============================================================

if __name__ == "__main__":
    tests = [
        test_display_timezone_hot_reload,
        test_copy_timezone_hot_reload,
        test_classify_hot_reload_tracker_domains,
        test_classify_hot_reload_meeting_domains,
        test_pulse_seconds_hot_reload,
        test_work_hints_hot_reload,
        test_include_notes_hot_reload,
        test_reinstall_hotkey_no_crash_without_ax,
        test_alarm_lifetime_hot_reload,
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
