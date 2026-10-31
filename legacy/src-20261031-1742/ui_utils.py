# src/ui_utils.py
"""Backwards compatibility: re-export from specialised modules.
New code should import from time_utils, color_utils, clipboard_utils directly.
"""

from clipboard_utils import (
    copy_events_to_clipboard,
    format_event_for_clipboard,
)
from color_utils import (
    get_calendar_color,
    get_event_color,
    get_status_color,
    get_week_gradient_color,
    interpolate_color,
    is_work_event,
)
from time_utils import (
    format_countdown,
    format_event_datetime,
    format_event_datetime_for_copy,
    format_time_delta,
    format_time_delta_compact,
    to_copy_tz,
    to_display_tz,
    to_msk,
)

__all__ = [
    "copy_events_to_clipboard",
    "format_event_for_clipboard",
    "get_calendar_color",
    "get_event_color",
    "get_status_color",
    "get_week_gradient_color",
    "interpolate_color",
    "is_work_event",
    "format_countdown",
    "format_event_datetime",
    "format_event_datetime_for_copy",
    "format_time_delta",
    "format_time_delta_compact",
    "to_copy_tz",
    "to_display_tz",
    "to_msk",
]
