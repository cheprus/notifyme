# ui_utils.py
from datetime import datetime
from AppKit import NSColor

def interpolate_color(c1, c2, t):
    return (c1[0]+(c2[0]-c1[0])*t, c1[1]+(c2[1]-c1[1])*t, c1[2]+(c2[2]-c1[2])*t)

def format_time_delta(minutes):
    if minutes < 1:
        return "less than a minute"
    h, m = int(minutes // 60), int(minutes % 60)
    if h > 0:
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    return f"{m}m"

def format_event_date(event_dt, now):
    delta_days = (event_dt.date() - now.date()).days
    if delta_days == 1:
        day_str = "Tomorrow"
    elif 2 <= delta_days <= 6:
        day_str = event_dt.strftime("%a")
    else:
        day_str = event_dt.strftime("%d.%m")
    return f"{day_str} {event_dt.strftime('%H:%M')}"

def format_event_line(ev, now, is_ongoing=False, is_finished=False):
    time_str = ev['start'].strftime('%H:%M')
    if is_ongoing:
        delta = int((now - ev['start']).total_seconds() // 60)
        return f"{time_str} · {ev['title']} (Ongoing {format_time_delta(delta)})"
    elif is_finished:
        delta = int((now - ev['end']).total_seconds() // 60)
        return f"{time_str} · {ev['title']} (Ended {format_time_delta(delta)} ago)"
    else:
        delta = (ev['start'] - now).total_seconds() / 60.0
        return f"{time_str} · {ev['title']} (In {format_time_delta(delta)})"

def get_gradient_color(delta_minutes, is_ongoing=False):
    if is_ongoing:
        t = min(delta_minutes, 120.0)
        if t <= 10:
            rgb = interpolate_color((1.0, 0.0, 0.0), (1.0, 0.4, 0.0), t / 10.0)
        elif t <= 30:
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.8, 0.0), (t - 10) / 20.0)
        elif t <= 60:
            rgb = interpolate_color((1.0, 0.8, 0.0), (0.7, 0.3, 1.0), (t - 30) / 30.0)
        else:
            rgb = interpolate_color((0.7, 0.3, 1.0), (0.5, 0.2, 0.7), min((t - 60) / 60.0, 1.0))
    else:
        t = min(delta_minutes, 180.0)
        if t <= 5:
            rgb = (1.0, 0.0, 0.0)
        elif t <= 30:
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.1, 0.3), (t - 5) / 25.0)
        elif t <= 60:
            rgb = interpolate_color((1.0, 0.1, 0.3), (1.0, 0.5, 0.6), (t - 30) / 30.0)
        elif t <= 120:
            rgb = interpolate_color((1.0, 0.5, 0.6), (0.6, 0.4, 1.0), (t - 60) / 60.0)
        else:
            rgb = interpolate_color((0.6, 0.4, 1.0), (0.0, 0.4, 1.0), min((t - 120) / 60.0, 1.0))
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], 1.0)

def get_week_gradient_color(index, total):
    t = index / (total - 1) if total > 1 else 0.0
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(0.5 + 0.35 * t, 0.3 + 0.4 * t, 0.8 + 0.2 * t, 1.0)

def get_status_color(events):
    now = datetime.now()
    if not events:
        return "No events", (0.2, 0.8, 0.2)
    next_future = None
    min_delta = float('inf')
    for ev in events:
        delta = (ev["start"] - now).total_seconds() / 60.0
        if 0 < delta < min_delta:
            min_delta = delta
            next_future = ev
    ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
    
    if next_future and min_delta <= 5:
        return f"In {format_time_delta(min_delta)}", (1.0, 0.0, 0.0)
    for ev in ongoing:
        m = int((now - ev["start"]).total_seconds() // 60)
        if m <= 10:
            return f"Ongoing {format_time_delta(m)}", (1.0, 0.0, 0.0)
    if next_future and min_delta <= 30:
        return f"In {format_time_delta(min_delta)}", (1.0, 0.1, 0.3)
    if next_future and min_delta <= 120:
        return f"In {format_time_delta(min_delta)}", (1.0, 0.5, 0.6)
    if ongoing:
        oldest = min(ongoing, key=lambda e: e["start"])
        return f"Ongoing {format_time_delta((now - oldest['start']).total_seconds() // 60)}", (0.6, 0.4, 1.0)
    if next_future:
        return f"In {format_time_delta(min_delta)}", (0.0, 0.4, 1.0)
    return "No events", (0.2, 0.8, 0.2)
