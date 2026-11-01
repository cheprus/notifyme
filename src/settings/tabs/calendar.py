# src/settings/tabs/calendar.py
"""Вкладка Calendar: target calendar, display/copy timezone, work hints."""

from AppKit import (
    NSBezelBorder,
    NSFont,
    NSMakeRect,
    NSScrollView,
    NSTextView,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
)

from calendar_service import list_calendars
from config import AVAILABLE_TIMEZONES, CONFIG

from ..rows import RowLayout, add_helper_and_advance, row_with_label
from ..widgets import make_button, make_label, make_popup

_HINTS_H = 100


class CalendarTab:
    def __init__(self, binding, store=None):
        self.binding = binding
        self.store = store
        self._callbacks = []
        self._view = None
        self._hints_view = None

    def view(self):
        if self._view is not None:
            return self._view

        w, h = 700, 480
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        v.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        layout = RowLayout(x=20, y_top=h - 20, width=w - 40)

        # ----- Target calendar -----
        row_with_label(v, layout, "Target calendar")
        cal_names = ["(default)"]
        try:
            cals = list_calendars(self.store) if self.store else []
            for c in cals:
                title = c.get("title")
                if title:
                    cal_names.append(title)
        except Exception as e:
            print(f"[SETTINGS] list_calendars failed: {e}", flush=True)

        current_cal = CONFIG.get("target_calendar_name", "") or ""
        current_label = current_cal if current_cal in cal_names else "(default)"
        y = layout.y + layout.row_gap
        popup_cal = make_popup(
            cal_names,
            NSMakeRect(layout.control_x, y, 300, 26),
            current_label,
            lambda i: self.binding.set(
                "target_calendar_name", "" if cal_names[i] == "(default)" else cal_names[i]
            ),
            self._callbacks,
        )
        v.addSubview_(popup_cal)
        add_helper_and_advance(
            v, layout,
            "(default) = системный календарь по умолчанию из Calendar.app.",
            self._callbacks,
        )

        # ----- Display timezone -----
        row_with_label(v, layout, "Timezone (display)")
        y = layout.y + layout.row_gap
        current_disp = CONFIG.get("display_timezone", "Local")
        disp_zones = list(AVAILABLE_TIMEZONES)
        if current_disp not in disp_zones:
            disp_zones.append(current_disp)
        popup_disp = make_popup(
            disp_zones,
            NSMakeRect(layout.control_x, y, 300, 26),
            current_disp,
            lambda i: self.binding.set("display_timezone", disp_zones[i]),
            self._callbacks,
        )
        v.addSubview_(popup_disp)
        add_helper_and_advance(
            v, layout,
            "Влияет на меню, alarm-окно и карточку. Local = системная TZ.",
            self._callbacks,
        )

        # ----- Copy timezone -----
        row_with_label(v, layout, "Timezone (copy)")
        y = layout.y + layout.row_gap
        current_copy = CONFIG.get("copy_timezone", "Local")
        copy_zones = list(AVAILABLE_TIMEZONES)
        if current_copy not in copy_zones:
            copy_zones.append(current_copy)
        popup_copy = make_popup(
            copy_zones,
            NSMakeRect(layout.control_x, y, 300, 26),
            current_copy,
            lambda i: self.binding.set("copy_timezone", copy_zones[i]),
            self._callbacks,
        )
        v.addSubview_(popup_copy)
        add_helper_and_advance(
            v, layout,
            "Влияет только на текст в буфере обмена (копирование событий).",
            self._callbacks,
        )

        # ----- Work calendar hints -----
        layout.y -= 10
        row_with_label(v, layout, "Work calendar hints")
        y = layout.y + layout.row_gap
        hints_text = "\n".join(CONFIG.get("work_calendar_hints", []) or [])

        # Уменьшаем ширину поля на 20px, чтобы был правый отступ от границы вкладки
        field_width_hints = max(100, layout.control_w - 20)

        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(layout.control_x, y - _HINTS_H, field_width_hints, _HINTS_H)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(NSBezelBorder)

        tv = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, field_width_hints, _HINTS_H)
        )
        tv.setFont_(NSFont.systemFontOfSize_(12))
        tv.setString_(hints_text)
        scroll.setDocumentView_(tv)
        v.addSubview_(scroll)
        self._hints_view = tv

        layout.y = y - _HINTS_H - layout.row_gap

        y = layout.next_y()
        save_btn = make_button(
            "Save hints",
            NSMakeRect(layout.control_x, y, 120, 26),
            self._save_hints,
            self._callbacks,
        )
        v.addSubview_(save_btn)

        hint = make_label(
            "Один hint на строку. Регистр не важен. Используется для подсветки work-событий.",
            NSMakeRect(layout.x, 16, layout.width, 16),
            secondary=True,
            size=11,
        )
        v.addSubview_(hint)

        self._view = v
        return v

    def _save_hints(self):
        if self._hints_view is None:
            return
        raw = self._hints_view.string()
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        seen = set()
        result = []
        for ln in lines:
            low = ln.lower()
            if low in seen:
                continue
            seen.add(low)
            result.append(ln)
        self.binding.set("work_calendar_hints", result)
        print(f"[SETTINGS] saved {len(result)} work hints", flush=True)
