# tests/test_logic_extra.py
import os
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ============================================================
# clipboard_utils
# ============================================================

def test_format_event_for_clipboard():
    from clipboard_utils import format_event_for_clipboard
    from config import CONFIG

    old = CONFIG.get("include_notes_in_copy", False)
    CONFIG["include_notes_in_copy"] = False
    try:
        msk = ZoneInfo("Europe/Moscow")
        now = datetime(2026, 10, 30, 10, 0, tzinfo=msk)
        ev = {
            "title": "MTS. #17702",
            "start": datetime(2026, 10, 30, 15, 30, tzinfo=msk),
            "url": "https://support.igtel.ru/issues/17702",
            "location": "https://mts-link.ru/j/1",
            "notes": "Описание",
        }
        s = format_event_for_clipboard(ev, now)
        assert "📅 Event: MTS. #17702" in s
        assert "🔗 https://support.igtel.ru/issues/17702" in s
        assert "📍 https://mts-link.ru/j/1" in s
        assert "📝" not in s

        CONFIG["include_notes_in_copy"] = True
        s = format_event_for_clipboard(ev, now)
        assert "📝 Описание" in s

        s = format_event_for_clipboard({"title": "X"}, now)
        assert "📅 Event: X" in s
        assert "🔗" not in s
        assert "📍" not in s
    finally:
        CONFIG["include_notes_in_copy"] = old


# ============================================================
# color_utils: get_status_color
# ============================================================

def test_get_status_color():
    from datetime import datetime as dt

    from color_utils import get_status_color

    # пусто
    text, rgb = get_status_color([])
    assert text == "No events"
    assert rgb == (0.2, 0.8, 0.2)

    now = dt.now()
    # встреча через 2 мин — красный
    start = now + timedelta(minutes=2)
    end = start + timedelta(minutes=30)
    text, rgb = get_status_color([{"start": start, "end": end}])
    assert "In" in text
    assert rgb[0] > 0.9  # красный

    # встреча через 20 мин — оранжевый
    start = now + timedelta(minutes=20)
    end = start + timedelta(minutes=30)
    text, rgb = get_status_color([{"start": start, "end": end}])
    assert "In" in text

    # встреча через 3 часа — жёлто-оранжевый (не синий!)
    start = now + timedelta(hours=3)
    end = start + timedelta(minutes=30)
    text, rgb = get_status_color([{"start": start, "end": end}])
    assert "In" in text
    assert rgb[0] > 0.9   # красный канал
    assert rgb[1] > 0.5   # зелёный канал (жёлтый = красный + зелёный)
    assert rgb[2] < 0.5   # синий канал низкий (не синий)

    # идёт сейчас — ongoing
    start = now - timedelta(minutes=5)
    end = now + timedelta(minutes=30)
    text, rgb = get_status_color([{"start": start, "end": end}])
    assert "Ongoing" in text


def test_get_event_color():
    from datetime import datetime as dt

    from color_utils import get_event_color

    now = dt.now()
    # ongoing — красный
    ev = {"start": now - timedelta(minutes=5), "end": now + timedelta(minutes=30)}
    c = get_event_color(ev, now)
    assert c.redComponent() > 0.9

    # tomorrow — синий
    tomorrow = (now + timedelta(days=1)).replace(hour=10, minute=0)
    ev = {"start": tomorrow, "end": tomorrow + timedelta(hours=1)}
    c = get_event_color(ev, now)
    assert c.blueComponent() > 0.5

    # week — нейтральный
    next_week = now + timedelta(days=5)
    ev = {"start": next_week, "end": next_week + timedelta(hours=1)}
    c = get_event_color(ev, now)
    assert abs(c.redComponent() - 0.65) < 0.1


# ============================================================
# time_utils: to_display_tz, to_copy_tz
# ============================================================

def test_to_display_tz():
    from config import CONFIG
    from time_utils import to_display_tz

    old = CONFIG.get("display_timezone")
    CONFIG["display_timezone"] = "Europe/Moscow"
    try:
        dt = datetime(2026, 10, 30, 15, 30)
        result = to_display_tz(dt)
        assert result.tzinfo is not None
        utc = ZoneInfo("UTC")
        dt_utc = datetime(2026, 10, 30, 12, 30, tzinfo=utc)
        result = to_display_tz(dt_utc)
        assert result.hour == 15
        assert to_display_tz(None) is None
    finally:
        CONFIG["display_timezone"] = old


def test_to_copy_tz():
    from config import CONFIG
    from time_utils import to_copy_tz

    old = CONFIG.get("copy_timezone")
    CONFIG["copy_timezone"] = "Europe/Moscow"
    try:
        utc = ZoneInfo("UTC")
        dt_utc = datetime(2026, 10, 30, 12, 30, tzinfo=utc)
        result = to_copy_tz(dt_utc)
        assert result.hour == 15
        assert to_copy_tz(None) is None
    finally:
        CONFIG["copy_timezone"] = old


# ============================================================
# calendar_service: _custom_patterns
# ============================================================

def test_custom_patterns():
    from calendar_service import _custom_patterns
    from config import CONFIG

    old = CONFIG.get("custom_tracker_domains")
    CONFIG["custom_tracker_domains"] = ["support.igtel.ru", "jira"]
    try:
        pats = _custom_patterns("custom_tracker_domains")
        assert len(pats) == 2
        assert "support" in pats[0]
    finally:
        CONFIG["custom_tracker_domains"] = old

    old = CONFIG.get("custom_meeting_domains")
    CONFIG["custom_meeting_domains"] = []
    try:
        assert _custom_patterns("custom_meeting_domains") == []
    finally:
        CONFIG["custom_meeting_domains"] = old


# ============================================================
# config: merge с дефолтами
# ============================================================

def test_config_merge_with_defaults():
    import config as cfg
    original_dir = cfg.CONFIG_DIR
    original_file = cfg.CONFIG_FILE
    with tempfile.TemporaryDirectory() as tmp:
        try:
            cfg.CONFIG_DIR = tmp
            cfg.CONFIG_FILE = os.path.join(tmp, "config.json")
            old_cfg = {
                "notify_minutes_before": 7,
                "sound_file": "/System/Library/Sounds/Ping.aiff",
            }
            cfg.save_config(old_cfg)
            loaded = cfg.load_config()
            assert loaded["notify_minutes_before"] == 7
            assert loaded.get("notify_minutes_after") == 2
            assert loaded.get("alarm_sound_on_seconds") == 12
            assert loaded.get("alarm_sound_off_seconds") == 60
            assert loaded.get("include_notes_in_copy") is False
        finally:
            cfg.CONFIG_DIR = original_dir
            cfg.CONFIG_FILE = original_file


# ============================================================
# alarm_utils: _resolve_sound_path_for
# ============================================================

def test_resolve_sound_path_for():
    from alarm_utils import _resolve_sound_path_for

    p = _resolve_sound_path_for("Hero")
    assert p is not None and "Hero" in p

    assert _resolve_sound_path_for("nonexistent-sound-xyz") is None
    assert _resolve_sound_path_for("") is None
    assert _resolve_sound_path_for(None) is None


# ============================================================
# runner
# ============================================================

if __name__ == "__main__":
    tests = [
        test_format_event_for_clipboard,
        test_get_status_color,
        test_get_event_color,
        test_to_display_tz,
        test_to_copy_tz,
        test_custom_patterns,
        test_config_merge_with_defaults,
        test_resolve_sound_path_for,
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
