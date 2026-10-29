# src/ui_utils.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from AppKit import NSColor

from config import CONFIG


# ---------- Таймзоны ----------

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
    """Приводит datetime к display_timezone (для меню/будильника/карточки)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(_display_tz())


def to_copy_tz(dt):
    """Приводит datetime к copy_timezone (только для копирования в буфер)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(_copy_tz())


def to_msk(dt):
    """Устаревшее имя, оставлено для совместимости."""
    return to_display_tz(dt)


# ---------- Форматирование ----------

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
    """Для меню/будильника/карточки — display_timezone."""
    return _format_datetime_in_tz(
        start_dt, now, to_display_tz,
        CONFIG.get("display_timezone", "Local")
    )


def format_event_datetime_for_copy(start_dt, now):
    """Только для копирования — copy_timezone."""
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


# ---------- Цвета ----------

def interpolate_color(c1, c2, t):
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    )


def is_work_event(ev):
    hints = CONFIG.get("work_calendar_hints", []) or []
    haystack = []
    for key in ("calendar_title", "title", "calendar"):
        v = ev.get(key)
        if v:
            haystack.append(str(v).lower())
    text = " ".join(haystack)
    for hint in hints:
        h = str(hint).lower()
        if h and h in text:
            return True
    return False


def _boost_color(rgb, factor=0.35):
    r, g, b = rgb
    avg = (r + g + b) / 3.0
    r = avg + (r - avg) * (1.0 + factor * 0.6)
    g = avg + (g - avg) * (1.0 + factor * 0.6)
    b = avg + (b - avg) * (1.0 + factor * 0.6)
    r = min(1.0, r * (1.0 + factor * 0.6))
    g = min(1.0, g * (1.0 + factor * 0.6))
    b = min(1.0, b * (1.0 + factor * 0.6))
    return (r, g, b)


def _rgb_ongoing():
    return (1.0, 0.15, 0.15)


def _rgb_upcoming(delta_minutes):
    t = min(max(delta_minutes, 0.0), 180.0)
    if t <= 5:
        return (1.0, 0.25, 0.15)
    elif t <= 30:
        return interpolate_color((1.0, 0.25, 0.15), (1.0, 0.55, 0.1), (t - 5) / 25.0)
    elif t <= 120:
        return interpolate_color((1.0, 0.55, 0.1), (1.0, 0.78, 0.15), (t - 30) / 90.0)
    else:
        return interpolate_color((1.0, 0.78, 0.15), (1.0, 0.88, 0.3), min((t - 120) / 60.0, 1.0))


def _rgb_tomorrow():
    return (0.2, 0.5, 1.0)


def _rgb_neutral():
    return (0.65, 0.65, 0.7)


def get_event_color(ev, now):
    start = ev.get("start")
    end = ev.get("end")
    if start is None:
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(0.65, 0.65, 0.7, 1.0)

    now_d = to_display_tz(now)
    start_d = to_display_tz(start)
    end_d = to_display_tz(end) if end is not None else None

    delta_min = (start_d - now_d).total_seconds() / 60.0

    if end_d is not None and start_d <= now_d <= end_d:
        rgb = _rgb_ongoing()
    elif start_d.date() == now_d.date() and delta_min > 0:
        rgb = _rgb_upcoming(delta_min)
    elif start_d.date() == now_d.date() + timedelta(days=1):
        rgb = _rgb_tomorrow()
    else:
        rgb = _rgb_neutral()

    if is_work_event(ev):
        rgb = _boost_color(rgb, factor=0.35)

    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], 1.0)


def get_status_color(events):
    now = to_display_tz(datetime.now())
    if not events:
        return "No events", (0.2, 0.8, 0.2)

    next_future = None
    min_delta = float('inf')
    for ev in events:
        delta = (to_display_tz(ev["start"]) - now).total_seconds() / 60.0
        if 0 < delta < min_delta:
            min_delta = delta
            next_future = ev

    ongoing = [
        ev for ev in events
        if to_display_tz(ev["start"]) <= now <= to_display_tz(ev["end"])
    ]

    def _maybe_boost(ev, rgb):
        if ev is not None and is_work_event(ev):
            return _boost_color(rgb, factor=0.35)
        return rgb

    if next_future and min_delta <= 5:
        rgb = _maybe_boost(next_future, _rgb_upcoming(min_delta))
        return f"In {format_time_delta_compact(min_delta)}", rgb
    for ev in ongoing:
        m = int((now - to_display_tz(ev["start"])).total_seconds() // 60)
        if m <= 10:
            rgb = _maybe_boost(ev, _rgb_ongoing())
            return f"Ongoing {format_time_delta_compact(m)}", rgb
    if next_future and min_delta <= 30:
        rgb = _maybe_boost(next_future, _rgb_upcoming(min_delta))
        return f"In {format_time_delta_compact(min_delta)}", rgb
    if next_future and min_delta <= 120:
        rgb = _maybe_boost(next_future, _rgb_upcoming(min_delta))
        return f"In {format_time_delta_compact(min_delta)}", rgb
    if ongoing:
        oldest = min(ongoing, key=lambda e: to_display_tz(e["start"]))
        m = int((now - to_display_tz(oldest['start'])).total_seconds() // 60)
        rgb = _maybe_boost(oldest, _rgb_ongoing())
        return f"Ongoing {format_time_delta_compact(m)}", rgb
    if next_future:
        rgb = _maybe_boost(next_future, _rgb_upcoming(min_delta))
        return f"In {format_time_delta_compact(min_delta)}", rgb
    return "No events", (0.2, 0.8, 0.2)


def get_week_gradient_color(index, total):
    rgb = _rgb_neutral()
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], 1.0)


def format_event_for_clipboard(ev, now):
    """Форматирование для буфера обмена — copy_timezone."""
    title = (ev.get('title') or 'Untitled').strip()
    text = f"📅 Event: {title}\n"
    if ev.get("start"):
        text += f"{format_event_datetime_for_copy(ev['start'], now)}\n"
    if ev.get("url"):
        text += f"🔗 {ev['url']}\n"
    if ev.get("location"):
        text += f"📍 {ev['location']}\n"
    return text
