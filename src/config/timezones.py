# src/config/timezones.py
import zoneinfo


def get_available_timezones():
    try:
        zones = sorted(zoneinfo.available_timezones())
    except Exception:
        zones = []
    return ["Local"] + zones


AVAILABLE_TIMEZONES = get_available_timezones()
