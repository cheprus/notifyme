# src/settings/binding.py
"""Мост между UI-контролами и CONFIG с дебаунсом и автосейвом."""

from collections.abc import Callable
from typing import Any

from Foundation import NSTimer

from config import CONFIG, DEFAULT_CONFIG, save_config

DEBOUNCE_SECONDS = 0.3


class ConfigBinding:
    def __init__(self, on_change: Callable[[], None] | None = None):
        self._on_change = on_change
        self._dirty = False
        self._timer = None
        self._pending_keys: set[str] = set()

    def get(self, key: str, default: Any = None) -> Any:
        return CONFIG.get(key, default)

    def set(self, key: str, value: Any) -> None:
        print(f"[DEBUG] binding.set: {key}={value}", flush=True)
        if CONFIG.get(key) == value:
            print(f"[DEBUG] binding.set: no change ({CONFIG.get(key)})", flush=True)
            return
        CONFIG[key] = value
        self._dirty = True
        self._pending_keys.add(key)
        self._schedule()

    def _schedule(self) -> None:
        if self._timer is not None:
            try:
                self._timer.invalidate()
            except Exception:
                pass
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            DEBOUNCE_SECONDS, self, "flush:", None, False
        )

    def flush_(self, timer=None) -> None:
        self.flush()

    def flush(self) -> None:
        if self._timer is not None:
            try:
                self._timer.invalidate()
            except Exception:
                pass
            self._timer = None
        if not self._dirty:
            print("[DEBUG] binding.flush: not dirty", flush=True)
            return
        save_config(CONFIG)
        self._dirty = False
        keys = sorted(self._pending_keys)
        self._pending_keys.clear()
        print(f"[SETTINGS] saved: {', '.join(keys)}", flush=True)
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception as e:
                print(f"[SETTINGS] on_change failed: {e}", flush=True)

    def reload_from_config(self) -> None:
        CONFIG.clear()
        CONFIG.update(DEFAULT_CONFIG)
        save_config(CONFIG)
        self._dirty = False
        self._pending_keys.clear()
        if self._timer is not None:
            try:
                self._timer.invalidate()
            except Exception:
                pass
            self._timer = None
        print("[SETTINGS] config reloaded from defaults", flush=True)
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception as e:
                print(f"[SETTINGS] on_change failed: {e}", flush=True)

    def force_save(self) -> None:
        self._dirty = True
        self.flush()
