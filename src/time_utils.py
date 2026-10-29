# src/time_utils.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import CONFIG


def _resolve_tz(name):
    if not name or name == "Local":
        return datetime.now().astimezone().tzinfo
    if name == "UTC":
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo


def _display_tz():
    return _resolve_tz(CONFIG.get("display_timezone", "Local"))


def _copy_tz():
    return _resolve_tz(CONFIG.get("copy_timezone", "Local"))


def to_display_tz(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(_display_tz())


def to_copy_tz(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(_copy_tz())


def to_msk(dt):
    return to_display_tz(dt)


def format_time_delta_compact(minutes):
    minutes = int(abs(minutes))
    if minutes < 1:
        return "0m"
    days = minutes // (24 * 60)
    hours = (minutes % (24 * 60)) // 60
    mins = minutes % 60
    if days > 0:
        return f"{days}d{hours}h" if hours > 0 else f"{days}d"
    if hours > 0:
        return f"{hours}h{mins}m" if mins > 0 else f"{hours}h"
    return f"{mins}m"


def format_time_delta(minutes):
    if minutes < 1:
        return "less than a minute"
    h, m = int(minutes // 60), int(minutes % 60)
    if h > 0:
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    return f"{m}m"


def _tz_suffix(tz_name):
    if tz_name == "Europe/Moscow":
        return "МСК"
    if tz_name == "UTC":
        return "UTC"
    if not tz_name or tz_name == "Local":
        return ""
    try:
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).strftime("%Z")
    except Exception:
        return ""


def _format_datetime_in_tz(start_dt, now, tz_func, tz_name):
    if start_dt is None:
        return ""
    start = tz_func(start_dt)
    now_local = tz_func(now)

    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months_ru = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    suffix = _tz_suffix(tz_name)

    if start.date() == now_local.date():
        base = f"Сегодня, {start.strftime('%H:%M')}"
    else:
        day_str = days_ru[start.weekday()]
        month_str = months_ru[start.month - 1]
        base = f"{day_str}, {start.day} {month_str}, {start.strftime('%H:%M')}"
    return f"{base} {suffix}".strip()


def format_event_datetime(start_dt, now):
    return _format_datetime_in_tz(
        start_dt, now, to_display_tz,
        CONFIG.get("display_timezone", "Local")
    )


def format_event_datetime_for_copy(start_dt, now):
    return _format_datetime_in_tz(
        start_dt, now, to_copy_tz,
        CONFIG.get("copy_timezone", "Local")
    )


def format_countdown(start, end, now):
    if start is None:
        return ""
    s = to_display_tz(start)
    n = to_display_tz(now)
    e = to_display_tz(end) if end is not None else None

    if e is not None and s <= n <= e:
        elapsed = (n - s).total_seconds() / 60.0
        return f"▶{format_time_delta_compact(elapsed)}"

    delta = (s - n).total_seconds() / 60.0
    if delta > 0:
        return format_time_delta_compact(delta)
    return f"−{format_time_delta_compact(delta)}"
