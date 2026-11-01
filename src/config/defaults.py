# src/config/defaults.py
from typing import Any

from .domains import KNOWN_MEETING_DOMAINS, KNOWN_TRACKER_DOMAINS

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
    "custom_tracker_domains": list(KNOWN_TRACKER_DOMAINS),
    "custom_meeting_domains": list(KNOWN_MEETING_DOMAINS),
    "tracker_base_url": "",
    "dnd_until": None,
    "alarm_sound_on_seconds": 12,
    "alarm_sound_off_seconds": 60,
    "include_notes_in_copy": False,
}

NOTIFY_BEFORE_PRESETS = [0, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 180]
NOTIFY_AFTER_PRESETS = [0, 1, 2, 3, 5, 10, 15, 30]
AUTO_CLOSE_PRESETS = [5, 10, 15, 30]
