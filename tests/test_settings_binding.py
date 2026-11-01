# tests/test_settings_binding.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _fresh_binding():
    """Возвращает (binding, reload_fn) — reload_fn откатывает CONFIG после теста."""
    from config import CONFIG
    saved = dict(CONFIG)
    from settings.binding import ConfigBinding

    def restore():
        CONFIG.clear()
        CONFIG.update(saved)

    return ConfigBinding(), restore


def test_set_updates_config_immediately():
    binding, restore = _fresh_binding()
    try:
        from config import CONFIG
        old = CONFIG.get("notify_minutes_before")
        binding.set("notify_minutes_before", 42)
        assert CONFIG["notify_minutes_before"] == 42
        binding.set("notify_minutes_before", old)
    finally:
        restore()


def test_set_noop_for_same_value():
    binding, restore = _fresh_binding()
    try:
        from config import CONFIG
        CONFIG["notify_minutes_before"] = 7
        calls = []

        def on_change():
            calls.append(1)

        binding._on_change = on_change
        binding.set("notify_minutes_before", 7)
        # значение не изменилось — on_change не должен сработать
        binding.flush()
        assert calls == []
    finally:
        restore()


def test_flush_saves_and_calls_on_change():
    binding, restore = _fresh_binding()
    try:
        from config import CONFIG, save_config
        calls = []
        binding._on_change = lambda: calls.append(1)
        binding.set("notify_minutes_before", 99)
        # до flush on_change не звался
        assert calls == []
        binding.flush()
        assert calls == [1]
        # save_config записал в файл — проверим через load_config
        from config.io import load_config
        loaded = load_config()
        assert loaded["notify_minutes_before"] == 99
        CONFIG["notify_minutes_before"] = 5
        save_config(CONFIG)
    finally:
        restore()


def test_flush_is_idempotent():
    binding, restore = _fresh_binding()
    try:
        calls = []
        binding._on_change = lambda: calls.append(1)
        binding.set("notify_minutes_before", 33)
        binding.flush()
        binding.flush()
        # второй flush без set — ничего не делает
        assert calls == [1]
    finally:
        restore()


def test_reload_from_config_resets_to_defaults():
    from config import CONFIG, DEFAULT_CONFIG
    saved = dict(CONFIG)
    try:
        CONFIG["notify_minutes_before"] = 999
        CONFIG["display_timezone"] = "Atlantis/Lost"
        from settings.binding import ConfigBinding
        binding = ConfigBinding()
        binding.reload_from_config()
        assert CONFIG["notify_minutes_before"] == DEFAULT_CONFIG["notify_minutes_before"]
        assert CONFIG["display_timezone"] == DEFAULT_CONFIG["display_timezone"]
    finally:
        CONFIG.clear()
        CONFIG.update(saved)


def test_reload_updates_dict_in_place():
    """CONFIG должен остаться тем же объектом — иначе другие модули потеряют ссылку."""
    from config import CONFIG
    saved = dict(CONFIG)
    try:
        ref_before = id(CONFIG)
        from settings.binding import ConfigBinding
        ConfigBinding().reload_from_config()
        assert id(CONFIG) == ref_before
    finally:
        CONFIG.clear()
        CONFIG.update(saved)


def test_debounce_timer_scheduled():
    """set() планирует NSTimer, flush_() инвалидирует."""
    binding, restore = _fresh_binding()
    try:
        binding.set("notify_minutes_before", 11)
        assert binding._timer is not None
        binding.flush()
        assert binding._timer is None
    finally:
        restore()


def test_force_save_writes_immediately():
    binding, restore = _fresh_binding()
    try:
        from config import CONFIG
        from config.io import load_config
        CONFIG["notify_minutes_before"] = 17
        binding.force_save()
        loaded = load_config()
        assert loaded["notify_minutes_before"] == 17
    finally:
        restore()


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
