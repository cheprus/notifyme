# src/config.py
import os, json
import zoneinfo

CONFIG_DIR = os.path.expanduser("~/.notifyme")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

DEFAULT_CONFIG = {
    "notify_minutes_before": 5,
    "auto_close_minutes": 15,
    "sound_file": "/System/Library/Sounds/Hero.aiff",
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
}

NOTIFY_BEFORE_PRESETS = [0, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 180]


def get_available_timezones():
    try:
        zones = sorted(zoneinfo.available_timezones())
    except Exception:
        zones = []
    return ["Local"] + zones


AVAILABLE_TIMEZONES = get_available_timezones()

AVAILABLE_SOUNDS = [
    "Glass", "Hero", "Ping", "Sosumi", "Submarine",
    "Tink", "Basso", "Funk", "Blow", "Bottle", "Frog",
    "Morse", "Pop", "Purr",
]


def ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    ensure_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
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
