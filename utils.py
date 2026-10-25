# utils.py
from datetime import datetime
from AppKit import NSColor

def interpolate_color(color1, color2, t):
    r = color1[0] + (color2[0] - color1[0]) * t
    g = color1[1] + (color2[1] - color1[1]) * t
    b = color1[2] + (color2[2] - color1[2]) * t
    return (r, g, b)

def format_time_delta(minutes):
    """Converts minutes to human-readable format (e.g., '7h 16m')."""
    if minutes < 1:
        return "less than a minute"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        if mins > 0:
            return f"{hours}h {mins}m"
        return f"{hours}h"
    return f"{mins}m"

def get_gradient_color(delta_minutes, is_ongoing=False):
    """
    Returns NSColor based on urgency gradient.
    """
    if is_ongoing:
        # Ongoing events: Red -> Orange -> Yellow -> Lavender -> Fading Purple
        t = min(delta_minutes, 120.0)
        if t <= 10:
            local_t = t / 10.0
            rgb = interpolate_color((1.0, 0.0, 0.0), (1.0, 0.4, 0.0), local_t)
        elif t <= 30:
            local_t = (t - 10) / 20.0
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.8, 0.0), local_t)
        elif t <= 60:
            local_t = (t - 30) / 30.0
            rgb = interpolate_color((1.0, 0.8, 0.0), (0.7, 0.3, 1.0), local_t)
        else:
            local_t = min((t - 60) / 60.0, 1.0)
            rgb = interpolate_color((0.7, 0.3, 1.0), (0.5, 0.2, 0.7), local_t)
    else:
        # Future events: Red -> Orange -> Magenta -> Pink -> Lavender -> Blue
        t = min(delta_minutes, 180.0)
        if t <= 5:
            rgb = (1.0, 0.0, 0.0)
        elif t <= 30:
            local_t = (t - 5) / 25.0
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.1, 0.3), local_t)
        elif t <= 60:
            local_t = (t - 30) / 30.0
            rgb = interpolate_color((1.0, 0.1, 0.3), (1.0, 0.5, 0.6), local_t)
        elif t <= 120:
            local_t = (t - 60) / 60.0
            rgb = interpolate_color((1.0, 0.5, 0.6), (0.6, 0.4, 1.0), local_t)
        else:
            local_t = min((t - 120) / 60.0, 1.0)
            rgb = interpolate_color((0.6, 0.4, 1.0), (0.0, 0.4, 1.0), local_t)
    
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], 1.0)

def get_status_color(events):
    """
    Returns (status_text, color) for the tray icon.
    """
    now = datetime.now()
    
    if not events:
        return "No events", (0.2, 0.8, 0.2) # Green

    next_future = None
    min_delta_future = float('inf')
    for ev in events:
        delta = (ev["start"] - now).total_seconds() / 60.0
        if delta > 0 and delta < min_delta_future:
            min_delta_future = delta
            next_future = ev

    ongoing_events = [ev for ev in events if ev["start"] <= now <= ev["end"]]

    # Urgent (Red)
    if next_future and min_delta_future <= 5:
        return f"In {format_time_delta(min_delta_future)}", (1.0, 0.0, 0.0)

    # Just started (Red)
    for ev in ongoing_events:
        minutes_ago = int((now - ev["start"]).total_seconds() // 60)
        if minutes_ago <= 10:
            return f"Ongoing {format_time_delta(minutes_ago)}", (1.0, 0.0, 0.0)

    # Soon (Crimson)
    if next_future and min_delta_future <= 30:
        return f"In {format_time_delta(min_delta_future)}", (1.0, 0.1, 0.3)

    # Not so soon (Pink)
    if next_future and min_delta_future <= 120:
        return f"In {format_time_delta(min_delta_future)}", (1.0, 0.5, 0.6)

    # Ongoing for a while (Lavender)
    if ongoing_events:
        oldest = min(ongoing_events, key=lambda e: e["start"])
        minutes_ago = int((now - oldest["start"]).total_seconds() // 60)
        return f"Ongoing {format_time_delta(minutes_ago)}", (0.6, 0.4, 1.0)

    # Far away (Blue)
    if next_future:
        return f"In {format_time_delta(min_delta_future)}", (0.0, 0.4, 1.0)

    return "No events", (0.2, 0.8, 0.2)
