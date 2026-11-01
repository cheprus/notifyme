# tests/test_classify.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_looks_like_url():
    from classify import looks_like_url
    assert looks_like_url("https://example.com") is True
    assert looks_like_url("http://example.com") is True
    assert looks_like_url("  https://example.com  ") is True
    assert looks_like_url("ftp://example.com") is False
    assert looks_like_url("example.com") is False
    assert looks_like_url("") is False
    assert looks_like_url(None) is False


def test_normalize_title_keeps_short():
    from classify import normalize_title
    assert normalize_title("A") == "A"
    assert normalize_title("  A  ") == "A"


def test_normalize_title_multiple_urls():
    from classify import normalize_title
    s = normalize_title("x https://a.com/issues/1 y https://b.com/issues/2")
    assert "#1" in s
    assert "#2" in s
    assert "https://a.com" not in s
    assert "https://b.com" not in s


def test_classify_url_priority_custom_over_builtin():
    """custom_meeting_domains важнее встроенного tracker-паттерна."""
    from classify import classify_url
    from config import CONFIG

    old = CONFIG.get("custom_meeting_domains")
    try:
        # github.com обычно tracker, но если пользователь добавил в meeting — побеждает custom
        CONFIG["custom_meeting_domains"] = ["github.com"]
        assert classify_url("https://github.com/org/repo") == "meeting"
    finally:
        CONFIG["custom_meeting_domains"] = old


def test_classify_url_custom_tracker():
    from classify import classify_url
    from config import CONFIG

    old = CONFIG.get("custom_tracker_domains")
    try:
        CONFIG["custom_tracker_domains"] = ["mycompany.example"]
        assert classify_url("https://mycompany.example/board/1") == "tracker"
    finally:
        CONFIG["custom_tracker_domains"] = old


def test_split_links_both_from_notes():
    from classify import split_links
    notes = (
        "Трекер https://support.igtel.ru/issues/1\n"
        "Встреча https://mts-link.ru/j/1"
    )
    tracker, meeting = split_links("", "", notes)
    assert "support.igtel.ru" in tracker
    assert "mts-link.ru" in meeting


def test_split_links_single_tracker_moved():
    from classify import split_links
    tracker, meeting = split_links("", "https://support.igtel.ru/issues/1", "")
    assert "support.igtel.ru" in tracker
    assert meeting == ""


def test_split_links_single_meeting_moved():
    from classify import split_links
    tracker, meeting = split_links("https://mts-link.ru/j/1", "", "")
    assert tracker == ""
    assert "mts-link.ru" in meeting


def test_split_links_both_unknown_kept():
    from classify import split_links
    tracker, meeting = split_links(
        "https://unknown-a.example/x",
        "https://unknown-b.example/y",
        "",
    )
    assert tracker == "https://unknown-a.example/x"
    assert meeting == "https://unknown-b.example/y"


def test_split_links_empty():
    from classify import split_links
    assert split_links("", "", "") == ("", "")
    assert split_links(None, None, None) == ("", "")


def test_split_links_tautoki_swapped():
    """URL=meeting, Location=tautoki (tracker) → свапнуть."""
    from classify import split_links
    tracker, meeting = split_links(
        "https://mts-link.ru/j/1",
        "https://tautoki.example/board/1",
        "",
    )
    assert "tautoki" in tracker
    assert "mts-link.ru" in meeting


def test_split_links_tautoki_correct():
    """URL=tautoki, Location=mts-link — не свапать."""
    from classify import split_links
    tracker, meeting = split_links(
        "https://tautoki.example/board/1",
        "https://mts-link.ru/j/1",
        "",
    )
    assert "tautoki" in tracker
    assert "mts-link.ru" in meeting


if __name__ == "__main__":
    tests = [
        test_looks_like_url,
        test_normalize_title_keeps_short,
        test_normalize_title_multiple_urls,
        test_classify_url_priority_custom_over_builtin,
        test_classify_url_custom_tracker,
        test_split_links_both_from_notes,
        test_split_links_single_tracker_moved,
        test_split_links_single_meeting_moved,
        test_split_links_both_unknown_kept,
        test_split_links_empty,
        test_split_links_tautoki_swapped,
        test_split_links_tautoki_correct,
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
