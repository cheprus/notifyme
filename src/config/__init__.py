# src/config/__init__.py
"""Config package: единая точка входа вместо старого src/config.py.

Все прежние импорты `from config import X` продолжают работать:
CONFIG, load_config, save_config, DEFAULT_CONFIG, CONFIG_DIR, CONFIG_FILE,
STATE_FILE, ensure_dir, NOTIFY_BEFORE_PRESETS, NOTIFY_AFTER_PRESETS,
AUTO_CLOSE_PRESETS, AVAILABLE_SOUNDS, AVAILABLE_TIMEZONES.
"""

from .defaults import (
    AUTO_CLOSE_PRESETS,
    DEFAULT_CONFIG,
    NOTIFY_AFTER_PRESETS,
    NOTIFY_BEFORE_PRESETS,
)
from .io import load_config, save_config
from .paths import CONFIG_DIR, CONFIG_FILE, STATE_FILE, ensure_dir
from .sounds import AVAILABLE_SOUNDS
from .timezones import AVAILABLE_TIMEZONES

# Единый живой объект: все модули читают/пишут один и тот же dict.
CONFIG = load_config()

__all__ = [
    "AUTO_CLOSE_PRESETS",
    "AVAILABLE_SOUNDS",
    "AVAILABLE_TIMEZONES",
    "CONFIG",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEFAULT_CONFIG",
    "NOTIFY_AFTER_PRESETS",
    "NOTIFY_BEFORE_PRESETS",
    "STATE_FILE",
    "ensure_dir",
    "load_config",
    "save_config",
]
