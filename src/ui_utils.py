# src/ui_utils.py
# Backwards compatibility: re-export from specialised modules.
# New code should import from time_utils, color_utils, clipboard_utils directly.

from time_utils import (
    to_display_tz,
    to_copy_tz,
    to_msk,
    format_time_delta_compact,
    format_time_delta,
    format_event_datetime,
    format_event_datetime_for_copy,
    format_countdown,
)

from color_utils import (
    interpolate_color,
    is_work_event,
    get_event_color,
    get_status_color,
    get_week_gradient_color,
    get_calendar_color,
)

from clipboard_utils import (
    format_event_for_clipboard,
    copy_events_to_clipboard,
)
