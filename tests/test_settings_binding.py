# tests/test_settings_binding.py
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Подменяет config.paths.CONFIG_FILE на tmp_path — тесты не трогают ~/.notifyme."""
    import config.paths as paths
    from config import CONFIG

    saved = dict(CONFIG)
    monkeypatch.setattr(paths, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_FILE", str(tmp_path / "state.json"))
    try:
        yield tmp_path
    finally:
        CONFIG.clear()
        CONFIG.update(saved)


def test_set_updates_config_immediately(isolated_config):
    from config import CONFIG
    from settings.binding import ConfigBinding

    binding = ConfigBinding()
    old = CONFIG.get("notify_minutes_before")
    binding.set("notify_minutes_before", 42)
    assert CONFIG["notify_minutes_before"] == 42
    binding.set("notify_minutes_before", old)


def test_set_noop_for_same_value(isolated_config):
    from config import CONFIG
    from settings.binding import ConfigBinding

    CONFIG["notify_minutes_before"] = 7
    calls = []
    binding = ConfigBinding()
    binding._on_change = lambda: calls.append(1)
    binding.set("notify_minutes_before", 7)
    binding.flush()
    assert calls == []


def test_flush_saves_and_calls_on_change(isolated_config):
    from config import CONFIG
    from config.io import load_config
    from settings.binding import ConfigBinding

    calls = []
    binding = ConfigBinding()
    binding._on_change = lambda: calls.append(1)
    binding.set("notify_minutes_before", 99)
    assert calls == []
    binding.flush()
    assert calls == [1]
    loaded = load_config()
    assert loaded["notify_minutes_before"] == 99


def test_flush_is_idempotent(isolated_config):
    from settings.binding import ConfigBinding

    calls = []
    binding = ConfigBinding()
    binding._on_change = lambda: calls.append(1)
    binding.set("notify_minutes_before", 33)
    binding.flush()
    binding.flush()
    assert calls == [1]


def test_reload_from_config_resets_to_defaults(isolated_config):
    from config import CONFIG, DEFAULT_CONFIG
    from settings.binding import ConfigBinding

    CONFIG["notify_minutes_before"] = 999
    CONFIG["display_timezone"] = "Atlantis/Lost"
    binding = ConfigBinding()
    binding.reload_from_config()
    assert CONFIG["notify_minutes_before"] == DEFAULT_CONFIG["notify_minutes_before"]
    assert CONFIG["display_timezone"] == DEFAULT_CONFIG["display_timezone"]


def test_reload_updates_dict_in_place(isolated_config):
    from config import CONFIG
    from settings.binding import ConfigBinding

    ref_before = id(CONFIG)
    ConfigBinding().reload_from_config()
    assert id(CONFIG) == ref_before


def test_debounce_timer_scheduled(isolated_config):
    from settings.binding import ConfigBinding

    binding = ConfigBinding()
    binding.set("notify_minutes_before", 11)
    assert binding._timer is not None
    binding.flush()
    assert binding._timer is None


def test_force_save_writes_immediately(isolated_config):
    from config import CONFIG
    from config.io import load_config
    from settings.binding import ConfigBinding

    CONFIG["notify_minutes_before"] = 17
    ConfigBinding().force_save()
    loaded = load_config()
    assert loaded["notify_minutes_before"] == 17


if __name__ == "__main__":
    tests = [
        test_set_updates_config_immediately,
        test_set_noop_for_same_value,
        test_flush_saves_and_calls_on_change,
        test_flush_is_idempotent,
        test_reload_from_config_resets_to_defaults,
        test_reload_updates_dict_in_place,
        test_debounce_timer_scheduled,
        test_force_save_writes_immediately,
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
