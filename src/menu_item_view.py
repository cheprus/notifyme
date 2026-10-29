# src/menu_item_view.py
import objc
from datetime import datetime, timedelta
from AppKit import (
    NSView, NSTextField, NSButton, NSColor, NSFont, NSMakeRect,
    NSBezelStyleShadowlessSquare, NSLineBreakByTruncatingTail,
    NSTextAlignmentLeft, NSTextAlignmentRight,
    NSBox, NSBoxCustom
)
from ui_utils import (
    get_event_color,
    format_countdown,
    to_display_tz,
)


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
    def initWithFrame_event_controller_(self, frame, event, controller):
        self = objc.super(MenuItemView, self).initWithFrame_(frame)
        if self is None:
            return None

        self.event = event
        self.controller = controller
        self._click_handler = self._on_row_click
        width = frame.size.width
        height = frame.size.height

        now = datetime.now()
        event_color = get_event_color(event, now)
        is_neutral = self._is_neutral_group(event, now)
        alpha = 0.35 if is_neutral else 1.0

        self.stripe = NSBox.alloc().initWithFrame_(NSMakeRect(3, 4, 3, height - 8))
        self.stripe.setBoxType_(NSBoxCustom)
        self.stripe.setBorderWidth_(0)
        self.stripe.setFillColor_(event_color.colorWithAlphaComponent_(alpha))
        self.stripe.setCornerRadius_(1.5)
        self.addSubview_(self.stripe)

        self.checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(12, (height - 20) / 2, 22, 20)
        )
        is_checked = event["id"] in controller.selected_ids
        self.checkbox.setTitle_("☑" if is_checked else "☐")
        self.checkbox.setBezelStyle_(NSBezelStyleShadowlessSquare)
        self.checkbox.setBordered_(False)
        self.checkbox.setFont_(NSFont.systemFontOfSize_(15))
        self.checkbox.setTarget_(self)
        self.checkbox.setAction_("toggleCheckbox:")
        self.addSubview_(self.checkbox)

        time_text = "—"
        start = event.get("start")
        if start is not None:
            time_text = to_display_tz(start).strftime("%H:%M")

        self.time_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(36, (height - 16) / 2, 44, 16)
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

        title_x = 84
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
        if start_date == today + timedelta(days=1):
            return False
        return True

    def toggleCheckbox_(self, sender):
        ev_id = self.event["id"]
        if ev_id in self.controller.selected_ids:
            self.controller.selected_ids.remove(ev_id)
            sender.setTitle_("☐")
        else:
            self.controller.selected_ids.add(ev_id)
            sender.setTitle_("☑")
        self.controller.copy_selected_to_clipboard()
