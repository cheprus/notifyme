# src/settings/__init__.py
"""Settings window: единая точка входа.

    from settings import show_settings
    show_settings(store, on_change=callback)

on_change вызывается после каждого сохранения в CONFIG (уже с дебаунсом).
"""

from .window import SettingsWindow

__all__ = ["SettingsWindow", "show_settings"]


def show_settings(store, on_change=None):
    """Открыть (или активировать) окно настроек."""
    SettingsWindow.show(store=store, on_change=on_change)
