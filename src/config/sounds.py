# src/config/sounds.py
import os

_SYSTEM_SOUNDS = [
    "Glass", "Hero", "Ping", "Sosumi", "Submarine",
    "Tink", "Basso", "Funk", "Blow", "Bottle", "Frog",
    "Morse", "Pop", "Purr",
]

_AUDIO_EXTS = (".mp3", ".wav", ".aiff")


def _candidate_dirs():
    """Каталоги, где ищем кастомные звуки. Порядок важен."""
    here = os.path.dirname(__file__)  # src/config (dev) или Contents/Frameworks/config (bundle)
    dirs = []

    env = os.environ.get("NOTIFYME_SOUNDS_DIR")
    if env:
        dirs.append(env)

    # ~/Library/Application Support/NotifyMe/sounds — можно докидывать без пересборки
    dirs.append(os.path.expanduser("~/Library/Application Support/NotifyMe/sounds"))

    # <app>/Contents/Resources/sounds — сюда install.py кладёт bundled-звуки
    # config/sounds.py → config → src(или Frameworks) → Contents
    config_dir = here
    parent = os.path.dirname(config_dir)          # src/  или Contents/Frameworks/
    grand = os.path.dirname(parent)               # <repo>/ или Contents/
    dirs.append(os.path.join(grand, "Resources", "sounds"))

    # dev-режим: src/sounds (рядом с config.py в старой раскладке)
    dirs.append(os.path.join(parent, "sounds"))
    # dev-режим: <repo>/assets/sounds
    dirs.append(os.path.join(grand, "assets", "sounds"))
    dirs.append(os.path.join(parent, "..", "assets", "sounds"))

    return dirs


def _get_custom_sounds():
    result = []
    for d in _candidate_dirs():
        try:
            if not os.path.isdir(d):
                continue
        except Exception:
            continue
        try:
            names = sorted(os.listdir(d))
        except Exception:
            continue
        for f in names:
            if f.lower().endswith(_AUDIO_EXTS) and f not in result:
                result.append(f)
    return result


AVAILABLE_SOUNDS = _SYSTEM_SOUNDS + _get_custom_sounds()
