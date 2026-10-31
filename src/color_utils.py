# src/color_utils.py
from datetime import datetime, timedelta

from AppKit import NSColor

from config import CONFIG
from time_utils import format_time_delta_compact, to_display_tz


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


_CALENDAR_PALETTE = [
    (0.30, 0.50, 1.00),
    (0.20, 0.70, 0.40),
    (1.00, 0.55, 0.15),
    (0.80, 0.30, 0.60),
    (0.20, 0.65, 0.75),
    (0.75, 0.45, 0.20),
    (0.55, 0.40, 0.85),
    (0.85, 0.70, 0.10),
    (0.90, 0.30, 0.30),
    (0.40, 0.60, 0.30),
]


def get_calendar_color(ev):
    cal = (ev.get("calendar_title") or "").strip()
    if not cal:
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(0.55, 0.55, 0.55, 1.0)

    h = 0
    for ch in cal:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    r, g, b = _CALENDAR_PALETTE[h % len(_CALENDAR_PALETTE)]

    if is_work_event(ev):
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)

    gray = 0.7
    r2 = r * 0.6 + gray * 0.4
    g2 = g * 0.6 + gray * 0.4
    b2 = b * 0.6 + gray * 0.4
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r2, g2, b2, 0.55)
