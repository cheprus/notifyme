# src/clipboard_utils.py
from AppKit import NSPasteboard

from time_utils import format_event_datetime_for_copy


def format_event_for_clipboard(ev, now):
    title = (ev.get('title') or 'Untitled').strip()
    text = f"📅 Event: {title}\n"
    if ev.get("start"):
        text += f"{format_event_datetime_for_copy(ev['start'], now)}\n"
    if ev.get("url"):
        text += f"🔗 {ev['url']}\n"
    if ev.get("location"):
        text += f"📍 {ev['location']}\n"
    return text


def copy_events_to_clipboard(events, now):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if not events:
        return 0
    text_parts = [format_event_for_clipboard(ev, now) for ev in events]
    full_text = "\n".join(text_parts)
    pb.setString_forType_(full_text, "public.utf8-plain-text")
    return len(events)
