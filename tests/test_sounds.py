# tests/test_sounds.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_available_sounds_contains_system():
    from config.sounds import AVAILABLE_SOUNDS
    assert "Glass" in AVAILABLE_SOUNDS
    assert "Ping" in AVAILABLE_SOUNDS
    assert "Hero" in AVAILABLE_SOUNDS


def test_available_sounds_no_duplicates():
    from config.sounds import AVAILABLE_SOUNDS
    assert len(AVAILABLE_SOUNDS) == len(set(AVAILABLE_SOUNDS))


def test_available_sounds_all_strings():
    from config.sounds import AVAILABLE_SOUNDS
    for s in AVAILABLE_SOUNDS:
        assert isinstance(s, str)
        assert s


def test_resolve_system_sound():
    from alarm_utils import _resolve_sound_path_for
    p = _resolve_sound_path_for("Glass")
    assert p is not None
    assert "Glass" in p
    assert os.path.exists(p)


def test_resolve_unknown_sound():
    from alarm_utils import _resolve_sound_path_for
    assert _resolve_sound_path_for("nonexistent-sound-xyz-12345") is None


def test_resolve_empty_sound():
    from alarm_utils import _resolve_sound_path_for
    assert _resolve_sound_path_for("") is None
    assert _resolve_sound_path_for(None) is None


def test_resolve_all_system_sounds():
    from alarm_utils import _resolve_sound_path_for
    from config.sounds import _SYSTEM_SOUNDS
    for s in _SYSTEM_SOUNDS:
        p = _resolve_sound_path_for(s)
        assert p is not None, f"system sound {s!r} not found on disk"
        assert os.path.exists(p)


def test_custom_sounds_from_env_dir(tmp_path, monkeypatch):
    """NOTIFYME_SOUNDS_DIR должен подхватывать mp3/wav из указанной папки."""
    monkeypatch.setenv("NOTIFYME_SOUNDS_DIR", str(tmp_path))
    (tmp_path / "a.mp3").write_bytes(b"")
    (tmp_path / "b.wav").write_bytes(b"")
    (tmp_path / "c.txt").write_text("nope")

    # Перезагружаем модуль, чтобы AVAILABLE_SOUNDS пересобрался с новым env
    import importlib

    import config.sounds as sounds_mod
    importlib.reload(sounds_mod)
    try:
        assert "a.mp3" in sounds_mod.AVAILABLE_SOUNDS
        assert "b.wav" in sounds_mod.AVAILABLE_SOUNDS
        assert "c.txt" not in sounds_mod.AVAILABLE_SOUNDS
    finally:
        monkeypatch.delenv("NOTIFYME_SOUNDS_DIR", raising=False)
        importlib.reload(sounds_mod)


def test_custom_sounds_assets_dir():
    """В dev-режиме assets/sounds должен находиться (если папка существует)."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assets = os.path.join(root, "assets", "sounds")
    if not os.path.isdir(assets):
        return  # нет папки — нечего проверять
    mp3s = [f for f in os.listdir(assets) if f.lower().endswith((".mp3", ".wav", ".aiff"))]
    if not mp3s:
        return  # папка пустая — нечего проверять
    from config.sounds import AVAILABLE_SOUNDS
    for f in mp3s:
        assert f in AVAILABLE_SOUNDS, f"{f!r} из assets/sounds не попал в AVAILABLE_SOUNDS"


if __name__ == "__main__":
    tests = [
        test_available_sounds_contains_system,
        test_available_sounds_no_duplicates,
        test_available_sounds_all_strings,
        test_resolve_system_sound,
        test_resolve_unknown_sound,
        test_resolve_empty_sound,
        test_resolve_all_system_sounds,
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
