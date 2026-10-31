# src/menu_item_view.py
from datetime import datetime, timedelta

import objc
from AppKit import (
    NSBezelStyleShadowlessSquare,
    NSButton,
    NSColor,
    NSFont,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSTextAlignmentLeft,
    NSTextAlignmentRight,
    NSTextField,
    NSView,
)

from ui_utils import format_countdown, get_calendar_color, get_event_color, is_work_event, to_display_tz


class ClickableView(NSView):
    def initWithFrame_click_(self, frame, click_handler):
        self = objc.super(ClickableView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._click_handler = click_handler
        return self

    def mouseDown_(self, event):
        if self._click_handler:
            self._click_handler()

    def acceptsFirstMouse_(self, event):
        return True


class MenuItemView(ClickableView):
    def initWithFrame_event_controller_showDate_(self, frame, event, controller, show_date=False):
        self = objc.super(MenuItemView, self).initWithFrame_(frame)
        if self is None:
            return None

        self.event = event
        self.controller = controller
        self._click_handler = self._on_row_click
        width = frame.size.width
        height = frame.size.height

        now = datetime.now()
        time_color = get_event_color(event, now)
        cal_color = get_calendar_color(event)
        is_work = is_work_event(event)
        is_neutral = self._is_neutral_group(event, now)
        time_alpha = 0.35 if is_neutral else 1.0

        stripe_h = height - 8
        stripe_y = 4
        stripe_w = 3

        self.stripe_time = NSView.alloc().initWithFrame_(
            NSMakeRect(3, stripe_y, stripe_w, stripe_h)
        )
        self.stripe_time.setWantsLayer_(True)
        if self.stripe_time.layer() is not None:
            self.stripe_time.layer().setBackgroundColor_(
                time_color.colorWithAlphaComponent_(time_alpha).CGColor()
            )
            self.stripe_time.layer().setCornerRadius_(1.5)
        self.addSubview_(self.stripe_time)

        self.stripe_cal = NSView.alloc().initWithFrame_(
            NSMakeRect(7, stripe_y, stripe_w, stripe_h)
        )
        self.stripe_cal.setWantsLayer_(True)
        if self.stripe_cal.layer() is not None:
            cal_alpha = 1.0 if is_work else 0.5
            if is_neutral:
                cal_alpha *= 0.6
            self.stripe_cal.layer().setBackgroundColor_(
                cal_color.colorWithAlphaComponent_(cal_alpha).CGColor()
            )
            self.stripe_cal.layer().setCornerRadius_(1.5)
        self.addSubview_(self.stripe_cal)

        self.checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(16, (height - 20) / 2, 22, 20)
        )
        is_checked = event["id"] in controller.selected_ids
        self.checkbox.setTitle_("☑" if is_checked else "☐")
        self.checkbox.setBezelStyle_(NSBezelStyleShadowlessSquare)
        self.checkbox.setBordered_(False)
        self.checkbox.setFont_(NSFont.systemFontOfSize_(15))
        self.checkbox.setTarget_(self)
        self.checkbox.setAction_("toggleCheckbox:")
        self.addSubview_(self.checkbox)

        start = event.get("start")
        if start is not None:
            start_disp = to_display_tz(start)
            if show_date:
                day_str = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][start_disp.weekday()]
                month_str = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"][start_disp.month - 1]
                time_text = f"{day_str}, {start_disp.day} {month_str} {start_disp.strftime('%H:%M')}"
                time_w = 130
            else:
                time_text = start_disp.strftime("%H:%M")
                time_w = 44
        else:
            time_text = "—"
            time_w = 44

        self.time_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(40, (height - 16) / 2, time_w, 16)
        )
        self.time_field.setStringValue_(time_text)
        self.time_field.setBezeled_(False)
        self.time_field.setDrawsBackground_(False)
        self.time_field.setEditable_(False)
        self.time_field.setSelectable_(False)
        self.time_field.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0.3))
        self.time_field.setTextColor_(NSColor.secondaryLabelColor())
        self.time_field.setAlignment_(NSTextAlignmentLeft)
        self.addSubview_(self.time_field)

        countdown_text = format_countdown(event.get("start"), event.get("end"), now)
        is_ongoing = countdown_text.startswith("▶")

        self.countdown_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(width - 82, (height - 16) / 2, 74, 16)
        )
        self.countdown_field.setStringValue_(countdown_text)
        self.countdown_field.setBezeled_(False)
        self.countdown_field.setDrawsBackground_(False)
        self.countdown_field.setEditable_(False)
        self.countdown_field.setSelectable_(False)
        self.countdown_field.setFont_(
            NSFont.monospacedDigitSystemFontOfSize_weight_(12, 0.5 if is_ongoing else 0.0)
        )
        if is_ongoing:
            self.countdown_field.setTextColor_(NSColor.systemRedColor())
        elif countdown_text.startswith("−"):
            self.countdown_field.setTextColor_(NSColor.tertiaryLabelColor())
        else:
            self.countdown_field.setTextColor_(NSColor.secondaryLabelColor())
        self.countdown_field.setAlignment_(NSTextAlignmentRight)
        self.addSubview_(self.countdown_field)

        title_x = 40 + time_w + 6
        title_w = width - title_x - 90
        self.text_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(title_x, (height - 16) / 2, title_w, 16)
        )
        title = (event.get("title") or "Untitled").strip()
        self.text_field.setStringValue_(title)
        self.text_field.setBezeled_(False)
        self.text_field.setDrawsBackground_(False)
        self.text_field.setEditable_(False)
        self.text_field.setSelectable_(False)
        if is_work:
            self.text_field.setFont_(NSFont.boldSystemFontOfSize_(13))
        else:
            self.text_field.setFont_(NSFont.systemFontOfSize_(13))
        self.text_field.setLineBreakMode_(NSLineBreakByTruncatingTail)
        self.text_field.setAlignment_(NSTextAlignmentLeft)
        self.addSubview_(self.text_field)

        return self

    def _on_row_click(self):
        try:
            self.controller.showEventCard_(self.event)
        except Exception as e:
            import traceback
            print(f"[DEBUG] showEventCard_ failed: {e}", flush=True)
            traceback.print_exc()

    def _is_neutral_group(self, ev, now):
        start = ev.get("start")
        if start is None:
            return True
        today = to_display_tz(now).date()
        start_date = to_display_tz(start).date()
        if start_date == today:
            return False
        return start_date != today + timedelta(days=1)

    def toggleCheckbox_(self, sender):
        ev_id = self.event["id"]
        if ev_id in self.controller.selected_ids:
            self.controller.selected_ids.remove(ev_id)
            sender.setTitle_("☐")
        else:
            self.controller.selected_ids.add(ev_id)
            sender.setTitle_("☑")
