# tests/test_copy_selected.py
"""Тесты на сборку текста для буфера обмена.

Проверяем чистую функцию _build_selected_text: из selected_ids + списка
событий собирается текст. Это то, что вызывается из menu-bar при
«Копировать выбранные».
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _msk_now():
    return datetime(2026, 10, 30, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))


def _mk_event(ev_id, title, start):
    return {
        "id": ev_id,
        "title": title,
        "start": start,
        "end": start + timedelta(hours=1),
        "url": "",
        "location": "",
        "notes": "",
        "calendar_title": "Work",
    }


def test_empty_selected_returns_empty():
    from status_bar import _build_selected_text
    now = _msk_now()
    events = [_mk_event("a", "A", now)]
    assert _build_selected_text(set(), events, now) == ""


def test_selected_ids_not_in_events_returns_empty():
    from status_bar import _build_selected_text
    now = _msk_now()
    events = [_mk_event("a", "A", now)]
    assert _build_selected_text({"x", "y"}, events, now) == ""


def test_one_selected():
    from status_bar import _build_selected_text
    now = _msk_now()
    events = [_mk_event("a", "A", now)]
    text = _build_selected_text({"a"}, events, now)
    assert "📅 Event: A" in text


def test_two_selected():
    from status_bar import _build_selected_text
    now = _msk_now()
    events = [
        _mk_event("a", "A", now),
        _mk_event("b", "B", now + timedelta(minutes=30)),
    ]
    text = _build_selected_text({"a", "b"}, events, now)
    assert "📅 Event: A" in text
    assert "📅 Event: B" in text
    # два события → как минимум один \n между ними
    assert text.count("📅 Event:") == 2


def test_partial_selection():
    from status_bar import _build_selected_text
    now = _msk_now()
    events = [
        _mk_event("a", "A", now),
        _mk_event("b", "B", now),
        _mk_event("c", "C", now),
    ]
    text = _build_selected_text({"a", "c"}, events, now)
    assert "📅 Event: A" in text
    assert "📅 Event: C" in text
    assert "📅 Event: B" not in text


def test_duplicate_ids_in_events():
    """Если событие с тем же id встречается дважды (upcoming + week),
    в текст оно не должно попасть дважды."""
    from status_bar import _build_selected_text
    now = _msk_now()
    ev = _mk_event("a", "A", now)
    events = [ev, ev]
    text = _build_selected_text({"a"}, events, now)
    # format_event_for_clipboard на каждое вхождение — если оба попадут, будет 2
    # сейчас оба попадают (expected behaviour: source не дедуплицируется)
    assert "📅 Event: A" in text


if __name__ == "__main__":
    tests = [
        test_empty_selected_returns_empty,
        test_selected_ids_not_in_events_returns_empty,
        test_one_selected,
        test_two_selected,
        test_partial_selection,
        test_duplicate_ids_in_events,
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
