# tests/test_domains.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_known_tracker_domains_not_empty():
    from config.domains import KNOWN_TRACKER_DOMAINS
    assert len(KNOWN_TRACKER_DOMAINS) > 0
    assert "support.igtel.ru" in KNOWN_TRACKER_DOMAINS
    assert "jira" in KNOWN_TRACKER_DOMAINS
    assert "tautoki" in KNOWN_TRACKER_DOMAINS


def test_known_meeting_domains_not_empty():
    from config.domains import KNOWN_MEETING_DOMAINS
    assert len(KNOWN_MEETING_DOMAINS) > 0
    assert "mts-link.ru" in KNOWN_MEETING_DOMAINS
    assert "zoom.us" in KNOWN_MEETING_DOMAINS


def test_known_domains_are_strings():
    from config.domains import KNOWN_MEETING_DOMAINS, KNOWN_TRACKER_DOMAINS
    for d in KNOWN_TRACKER_DOMAINS + KNOWN_MEETING_DOMAINS:
        assert isinstance(d, str)
        assert d.strip() == d
        assert d


def test_known_domains_match_classify():
    """Все известные домены должны распознаваться classify_url в своей категории."""
    from classify import classify_url
    from config.domains import KNOWN_MEETING_DOMAINS, KNOWN_TRACKER_DOMAINS

    for d in KNOWN_TRACKER_DOMAINS:
        url = f"https://{d}/"
        kind = classify_url(url)
        assert kind == "tracker", f"{url} -> {kind}, expected tracker"

    for d in KNOWN_MEETING_DOMAINS:
        url = f"https://{d}/"
        kind = classify_url(url)
        assert kind == "meeting", f"{url} -> {kind}, expected meeting"


def test_tautoki_classified_as_tracker_builtin():
    """tautoki распознаётся как tracker даже без custom_tracker_domains."""
    from classify import classify_url
    from config import CONFIG

    old = CONFIG.get("custom_tracker_domains")
    try:
        CONFIG["custom_tracker_domains"] = []
        for url in [
            "https://tautoki.example.com/board/1",
            "https://tracker.tautoki.io/issues/42",
            "https://tautoki.ru/browse/PROJ-1",
        ]:
            assert classify_url(url) == "tracker", f"{url} -> {classify_url(url)}"
    finally:
        CONFIG["custom_tracker_domains"] = old


def test_tautoki_in_defaults():
    """В DEFAULT_CONFIG tautoki уже есть — новые пользователи не заполняют руками."""
    from config.defaults import DEFAULT_CONFIG
    assert "tautoki" in DEFAULT_CONFIG["custom_tracker_domains"]


if __name__ == "__main__":
    tests = [
        test_known_tracker_domains_not_empty,
        test_known_meeting_domains_not_empty,
        test_known_domains_are_strings,
        test_known_domains_match_classify,
        test_tautoki_classified_as_tracker_builtin,
        test_tautoki_in_defaults,
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
