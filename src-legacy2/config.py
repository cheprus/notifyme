# src/config.py
import json
import os
import zoneinfo
from typing import Any

CONFIG_DIR = os.environ.get("NOTIFYME_CONFIG_DIR") or os.path.expanduser("~/.notifyme")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

# Явный тип, чтобы DEFAULT_CONFIG["work_calendar_hints"] был list[str], а не object
DEFAULT_CONFIG: dict[str, Any] = {
    "notify_minutes_before": 5,
    "notify_minutes_after": 2,
    "snooze_minutes": 5,
    "auto_close_minutes": 15,
    "sound_file": "droid-meeting.mp3",
    "sound_output_device": "Default",
    "display_timezone": "Local",
    "copy_timezone": "Europe/Moscow",
    "target_calendar_name": "",
    "work_calendar_hints": [
        "work", "event", "job",
        "рабо", "встреч", "mts", "corp", "office",
    ],
    "custom_tracker_domains": [],
    "custom_meeting_domains": [],
    "tracker_base_url": "",
    "dnd_until": None,
    "alarm_sound_on_seconds": 12,
    "alarm_sound_off_seconds": 60,
    "include_notes_in_copy": False,
}

NOTIFY_BEFORE_PRESETS = [0, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 180]
NOTIFY_AFTER_PRESETS = [0, 1, 2, 3, 5, 10, 15, 30]
AUTO_CLOSE_PRESETS = [5, 10, 15, 30]


def get_available_timezones():
    try:
        zones = sorted(zoneinfo.available_timezones())
    except Exception:
        zones = []
    return ["Local"] + zones


AVAILABLE_TIMEZONES = get_available_timezones()

_SYSTEM_SOUNDS = [
    "Glass", "Hero", "Ping", "Sosumi", "Submarine",
    "Tink", "Basso", "Funk", "Blow", "Bottle", "Frog",
    "Morse", "Pop", "Purr",
]


def _get_custom_sounds():
    candidates = [
        os.path.join(os.path.dirname(__file__), "sounds"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "sounds"),
    ]
    result = []
    for d in candidates:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".mp3", ".wav", ".aiff")) and f not in result:
                result.append(f)
    return result


AVAILABLE_SOUNDS = _SYSTEM_SOUNDS + _get_custom_sounds()


def ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    ensure_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            merged = {**DEFAULT_CONFIG}
            for k, v in data.items():
                merged[k] = v
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


CONFIG = load_config()
