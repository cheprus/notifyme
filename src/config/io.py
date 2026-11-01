# src/config/io.py
import json
import os

from .defaults import DEFAULT_CONFIG
from .paths import CONFIG_FILE, ensure_dir


def _coerce_types(merged: dict) -> dict:
    if not isinstance(merged.get("work_calendar_hints"), list):
        merged["work_calendar_hints"] = list(DEFAULT_CONFIG["work_calendar_hints"])
    if not isinstance(merged.get("custom_tracker_domains"), list):
        merged["custom_tracker_domains"] = []
    if not isinstance(merged.get("custom_meeting_domains"), list):
        merged["custom_meeting_domains"] = []
    if not isinstance(merged.get("target_calendar_name"), str):
        merged["target_calendar_name"] = ""
    if not isinstance(merged.get("tracker_base_url"), str):
        merged["tracker_base_url"] = ""
    if "dnd_until" not in merged:
        merged["dnd_until"] = None
    if not isinstance(merged.get("alarm_sound_on_seconds"), int):
        merged["alarm_sound_on_seconds"] = 12
    if not isinstance(merged.get("alarm_sound_off_seconds"), int):
        merged["alarm_sound_off_seconds"] = 60
    if not isinstance(merged.get("include_notes_in_copy"), bool):
        merged["include_notes_in_copy"] = False
    if not isinstance(merged.get("notify_minutes_after"), int):
        merged["notify_minutes_after"] = 2
    if not isinstance(merged.get("snooze_minutes"), int):
        merged["snooze_minutes"] = 5
    return merged


def load_config():
    ensure_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            merged = {**DEFAULT_CONFIG, **data}
            return _coerce_types(merged)
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(config):
    ensure_dir()
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
