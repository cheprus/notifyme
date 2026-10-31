# src/add_event_window.py
import datetime
import re
import subprocess
from datetime import datetime as dt
from types import ModuleType
from typing import Any

import objc
from AppKit import (
    NSAlert,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSBezelBorder,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSDatePicker,
    NSDatePickerElementFlagHourMinute,
    NSDatePickerElementFlagYearMonthDay,
    NSDatePickerModeSingle,
    NSDatePickerStyleTextFieldAndStepper,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSPasteboard,
    NSScreenSaverWindowLevel,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowStyleMaskTitled,
)
from Foundation import NSApplication, NSDate, NSObject

from calendar_service import _log, classify_url, create_event_via_applescript

# audio_output может быть ModuleType или None
audio_output: ModuleType | None
try:
    import audio_output  # noqa: F401
except ImportError:
    audio_output = None

# Ключ — id(panel)
_RETAINED_HANDLERS: dict[int, Any] = {}


class FormHandler(NSObject):
    def initWithAction_(self, action):
        self = objc.super(FormHandler, self).init()
        if self is None:
            return None
        self.action = action
        return self

    def performAction_(self, sender):
        self.action()


def parse_clipboard(text):
    result = {"title": "", "video_url": "", "url": "", "notes": ""}
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    title_match = re.search(r'Title:\s*(.+)', text, re.IGNORECASE)
    if title_match:
        title_text = title_match.group(1).strip()
    else:
        title_text = ""
        for line in lines:
            if (
                not re.match(r'^(When|Location|Organizer|Description|Attendees):', line, re.IGNORECASE)
                and not re.match(r'^[A-Z][a-z]+, [A-Z][a-z]+ \d+, \d{4}', line)
            ):
                title_text = line
                break

    if title_text.startswith("http"):
        result["title"] = title_text
        result["url"] = title_text
    else:
        result["title"] = title_text

    all_links = re.findall(r'https?://[^\s<>"\']+', text)
    for link in all_links:
        kind = classify_url(link)
        if kind == 'meeting' and not result["video_url"]:
            result["video_url"] = link
        elif kind == 'tracker' and not result["url"]:
            result["url"] = link
        elif kind == 'unknown':
            if not result["url"]:
                result["url"] = link
            elif not result["video_url"]:
                result["video_url"] = link

    loc_match = re.search(r'Location:\s*(.+)', text, re.IGNORECASE)
    if loc_match:
        loc_text = loc_match.group(1).strip()
        if loc_text.startswith("http") and not result["video_url"]:
            result["video_url"] = loc_text

    desc_match = re.search(r'Description:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        result["notes"] = desc_match.group(1).strip()

    return result


def create_label(text, frame, bold=False, size=12, secondary=True):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    if bold:
        label.setFont_(NSFont.boldSystemFontOfSize_(size))
    else:
        label.setFont_(NSFont.systemFontOfSize_(size))
    if secondary:
        label.setTextColor_(NSColor.secondaryLabelColor())
    else:
        label.setTextColor_(NSColor.labelColor())
    return label


def _safe_activate(app):
    try:
        if hasattr(app, "activateIgnoringOtherApps_"):
            app.activateIgnoringOtherApps_(True)
            return
    except Exception as e:
        print(f"[DEBUG] activateIgnoringOtherApps_ failed: {e}", flush=True)
    try:
        if hasattr(app, "activate"):
            app.activate()
            return
    except Exception as e:
        print(f"[DEBUG] activate() failed: {e}", flush=True)


def main(as_child=False):
    """as_child=True — вызывается из status_bar, не запускает app.run() и не убивает приложение."""
    print(f"[DEBUG] add_event_window.main(as_child={as_child})", flush=True)
    app = NSApplication.sharedApplication()

    original_policy = app.activationPolicy()
    try:
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    except Exception as e:
        print(f"[DEBUG] setActivationPolicy(Regular) failed: {e}", flush=True)
    _safe_activate(app)

    width, height = 600, 680
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height), NSWindowStyleMaskTitled,
        NSBackingStoreBuffered, False
    )
    panel.setTitle_("New Event")
    panel.center()
    panel.setReleasedWhenClosed_(False)
    panel.setLevel_(NSScreenSaverWindowLevel)
    panel.setTitlebarAppearsTransparent_(True)

    effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    effect.setMaterial_(NSVisualEffectMaterialHUDWindow)
    effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    effect.setState_(NSVisualEffectStateActive)
    effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    panel.setContentView_(effect)
    content = effect

    pb = NSPasteboard.generalPasteboard()
    clipboard_text = pb.stringForType_("public.utf8-plain-text") or ""
    parsed = parse_clipboard(clipboard_text)

    margin_left = 20
    label_width = 130
    field_left = margin_left + label_width + 10
    field_width = width - field_left - margin_left
    y = height - 40
    row_gap = 46

    # Title
    content.addSubview_(create_label("Title:", NSMakeRect(margin_left, y + 6, label_width, 18)))
    field_title = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, y, field_width, 26))
    field_title.setStringValue_(parsed["title"])
    field_title.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_title)
    y -= row_gap

    # Start
    content.addSubview_(create_label("Start:", NSMakeRect(margin_left, y + 6, label_width, 18)))
    date_picker = NSDatePicker.alloc().initWithFrame_(NSMakeRect(field_left, y, field_width, 28))
    date_picker.setDatePickerStyle_(NSDatePickerStyleTextFieldAndStepper)
    date_picker.setDatePickerMode_(NSDatePickerModeSingle)
    date_picker.setDatePickerElements_(NSDatePickerElementFlagYearMonthDay | NSDatePickerElementFlagHourMinute)
    date_picker.setFont_(NSFont.systemFontOfSize_(13))

    date_match = re.search(r'(\w+,\s*\w+\s*\d+,\s*\d{4},\s*\d{2}:\d{2})', clipboard_text)
    if date_match:
        try:
            dt_obj = dt.strptime(date_match.group(1), "%A, %B %d, %Y, %H:%M")
            date_picker.setDateValue_(NSDate.dateWithTimeIntervalSince1970_(dt_obj.timestamp()))
        except Exception:
            pass
    else:
        now = dt.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        date_picker.setDateValue_(NSDate.dateWithTimeIntervalSince1970_(next_hour.timestamp()))

    content.addSubview_(date_picker)
    y -= row_gap

    # Duration
    content.addSubview_(create_label("Duration (min):", NSMakeRect(margin_left, y + 6, label_width, 18)))
    field_dur = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, y, 100, 26))
    field_dur.setStringValue_("120")
    field_dur.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_dur)
    y -= row_gap

    # Location
    content.addSubview_(create_label("Location (встреча):", NSMakeRect(margin_left, y + 6, label_width, 18)))
    field_location = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, y, field_width, 26))
    field_location.setStringValue_(parsed["video_url"])
    field_location.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_location)
    y -= row_gap

    # URL
    content.addSubview_(create_label("URL (трекер):", NSMakeRect(margin_left, y + 6, label_width, 18)))
    field_url = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, y, field_width, 26))
    field_url.setStringValue_(parsed["url"])
    field_url.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_url)
    y -= row_gap + 10

    # Notes
    content.addSubview_(create_label("Notes:", NSMakeRect(margin_left, y + 6, label_width, 18)))
    scroll_view = NSScrollView.alloc().initWithFrame_(NSMakeRect(field_left, y - 90, field_width, 90))
    scroll_view.setHasVerticalScroller_(True)
    scroll_view.setBorderType_(NSBezelBorder)
    text_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, field_width, 90))
    text_view.setEditable_(True)
    text_view.setFont_(NSFont.systemFontOfSize_(13))
    text_view.setString_(parsed["notes"])
    scroll_view.setDocumentView_(text_view)
    content.addSubview_(scroll_view)

    def close_panel():
        try:
            panel.orderOut_(None)
            panel.close()
        except Exception:
            pass
        _RETAINED_HANDLERS.pop(id(panel), None)
        if as_child:
            try:
                app.setActivationPolicy_(original_policy)
            except Exception:
                pass

    def paste_from_clipboard():
        pb_local = NSPasteboard.generalPasteboard()
        current = pb_local.stringForType_("public.utf8-plain-text") or ""
        if not current:
            return
        p = parse_clipboard(current)
        field_title.setStringValue_(p["title"])
        field_location.setStringValue_(p["video_url"])
        field_url.setStringValue_(p["url"])
        text_view.setString_(p["notes"])

    paste_btn = NSButton.alloc().initWithFrame_(NSMakeRect(margin_left, 20, 150, 32))
    paste_btn.setTitle_("📋 Paste from Clipboard")
    paste_btn.setBezelStyle_(NSBezelStyleRounded)
    paste_btn.setFont_(NSFont.boldSystemFontOfSize_(12))
    paste_handler = FormHandler.alloc().initWithAction_(paste_from_clipboard)
    paste_btn.setTarget_(paste_handler)
    paste_btn.setAction_("performAction:")
    content.addSubview_(paste_btn)

    def save_action():
        ev_title = field_title.stringValue()
        ev_meeting = field_location.stringValue()
        ev_tracker = field_url.stringValue()
        ev_notes = text_view.string()
        ev_start = date_picker.dateValue()
        ev_dur_min = float(field_dur.stringValue() or 30)

        start_dt = dt.fromtimestamp(ev_start.timeIntervalSince1970())
        end_dt = start_dt + datetime.timedelta(minutes=ev_dur_min)

        _log(f"SAVE CLICKED: title={ev_title!r} start={start_dt} dur={ev_dur_min}")

        success, error = create_event_via_applescript(
            ev_title, start_dt, end_dt, ev_notes, ev_tracker, ev_meeting
        )
        _log(f"SAVE RESULT: success={success} error={error!r}")

        if success:
            try:
                subprocess.Popen(["open", "-a", "Calendar"])
            except Exception as e:
                _log(f"Failed to open Calendar.app: {e}")
            if as_child:
                close_panel()
            else:
                app.terminate_(None)
        else:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Failed to save event")
            alert.setInformativeText_(f"Error: {error}\n\nSee /tmp/notifyme_debug.log for details.")
            alert.setAlertStyle_(2)
            alert_window = alert.window()
            alert_window.setLevel_(NSScreenSaverWindowLevel)
            try:
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            except Exception:
                pass
            alert_window.makeKeyAndOrderFront_(None)
            alert.runModal()
            if as_child:
                close_panel()
            else:
                app.terminate_(None)

    def cancel_action():
        if as_child:
            close_panel()
        else:
            app.terminate_(None)

    save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 240, 20, 100, 32))
    save_btn.setTitle_("Save")
    save_btn.setBezelStyle_(NSBezelStyleRounded)
    save_btn.setFont_(NSFont.boldSystemFontOfSize_(13))
    save_handler = FormHandler.alloc().initWithAction_(save_action)
    save_btn.setTarget_(save_handler)
    save_btn.setAction_("performAction:")
    content.addSubview_(save_btn)

    cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 130, 20, 100, 32))
    cancel_btn.setTitle_("Cancel")
    cancel_btn.setBezelStyle_(NSBezelStyleRounded)
    cancel_btn.setFont_(NSFont.systemFontOfSize_(12))
    cancel_handler = FormHandler.alloc().initWithAction_(cancel_action)
    cancel_btn.setTarget_(cancel_handler)
    cancel_btn.setAction_("performAction:")
    content.addSubview_(cancel_btn)

    _RETAINED_HANDLERS[id(panel)] = {
        "paste": paste_handler,
        "save": save_handler,
        "cancel": cancel_handler,
    }

    panel.makeKeyAndOrderFront_(None)
    panel.orderFrontRegardless()
    print(f"[DEBUG] panel shown: isVisible={panel.isVisible()}, isKey={panel.isKeyWindow()}", flush=True)

    if as_child:
        return
    app.run()
    _RETAINED_HANDLERS.pop(id(panel), None)


if __name__ == "__main__":
    main()
