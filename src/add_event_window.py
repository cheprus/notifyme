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
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSPasteboard,
    NSScreenSaverWindowLevel,
    NSScrollView,
    NSTabView,
    NSTabViewItem,
    NSTextField,
    NSTextView,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialSidebar,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSApplication, NSDate, NSObject

import strings as S
from calendar_service import _log, classify_url, create_event_via_applescript

audio_output: ModuleType | None
try:
    import audio_output  # noqa: F401
except ImportError:
    audio_output = None

_RETAINED_HANDLERS: dict[int, Any] = {}

_WINDOW_W = 600
_WINDOW_H = 560
_TAB_PADDING = 12


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
        app.activateIgnoringOtherApps_(True)
    except Exception:
        try:
            app.activate()
        except Exception:
            pass


def _build_event_tab(content, parsed, w, h, on_save, on_cancel, on_paste):
    """Строит содержимое вкладки Event. Title прижат к верху, Notes — к кнопкам."""
    margin_left = 20
    label_width = 130
    field_left = margin_left + label_width + 10
    field_width = w - field_left - margin_left

    notes_h = 140
    btn_y = 20
    notes_y = btn_y + 32 + 10         # 62

    title_y = h - 60
    start_y = title_y - 40
    duration_y = start_y - 40
    location_y = duration_y - 40
    url_y = location_y - 40

    widgets = {}

    # Title
    content.addSubview_(create_label("Title:", NSMakeRect(margin_left, title_y + 6, label_width, 18)))
    field_title = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, title_y, field_width, 26))
    field_title.setStringValue_(parsed["title"])
    field_title.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_title)
    widgets["title"] = field_title

    # Start
    content.addSubview_(create_label("Start:", NSMakeRect(margin_left, start_y + 6, label_width, 18)))
    date_picker = NSDatePicker.alloc().initWithFrame_(NSMakeRect(field_left, start_y, field_width, 28))
    date_picker.setDatePickerStyle_(NSDatePickerStyleTextFieldAndStepper)
    date_picker.setDatePickerMode_(NSDatePickerModeSingle)
    date_picker.setDatePickerElements_(NSDatePickerElementFlagYearMonthDay | NSDatePickerElementFlagHourMinute)
    date_picker.setFont_(NSFont.systemFontOfSize_(13))

    clipboard_text = NSPasteboard.generalPasteboard().stringForType_("public.utf8-plain-text") or ""
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
    widgets["start"] = date_picker

    # Duration
    content.addSubview_(create_label("Duration (min):", NSMakeRect(margin_left, duration_y + 6, label_width, 18)))
    field_dur = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, duration_y, 100, 26))
    field_dur.setStringValue_("120")
    field_dur.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_dur)
    widgets["duration"] = field_dur

    # Location (meeting)
    content.addSubview_(create_label("Location (встреча):", NSMakeRect(margin_left, location_y + 6, label_width, 18)))
    field_location = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, location_y, field_width, 26))
    field_location.setStringValue_(parsed["video_url"])
    field_location.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_location)
    widgets["location"] = field_location

    # URL (tracker)
    content.addSubview_(create_label("URL (трекер):", NSMakeRect(margin_left, url_y + 6, label_width, 18)))
    field_url = NSTextField.alloc().initWithFrame_(NSMakeRect(field_left, url_y, field_width, 26))
    field_url.setStringValue_(parsed["url"])
    field_url.setFont_(NSFont.systemFontOfSize_(13))
    content.addSubview_(field_url)
    widgets["url"] = field_url

    # Notes
    content.addSubview_(create_label("Notes:", NSMakeRect(margin_left, notes_y + notes_h - 18, label_width, 18)))
    scroll_view = NSScrollView.alloc().initWithFrame_(
        NSMakeRect(field_left, notes_y, field_width, notes_h)
    )
    scroll_view.setHasVerticalScroller_(True)
    scroll_view.setBorderType_(NSBezelBorder)
    text_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, field_width, notes_h))
    text_view.setEditable_(True)
    text_view.setFont_(NSFont.systemFontOfSize_(13))
    text_view.setString_(parsed["notes"])
    scroll_view.setDocumentView_(text_view)
    content.addSubview_(scroll_view)
    widgets["notes"] = text_view

    # Buttons
    paste_btn = NSButton.alloc().initWithFrame_(NSMakeRect(margin_left, btn_y, 150, 32))
    paste_btn.setTitle_(S.ADD_EVENT_BTN_PASTE)
    paste_btn.setBezelStyle_(NSBezelStyleRounded)
    paste_btn.setFont_(NSFont.boldSystemFontOfSize_(12))
    paste_handler = FormHandler.alloc().initWithAction_(on_paste)
    paste_btn.setTarget_(paste_handler)
    paste_btn.setAction_("performAction:")
    content.addSubview_(paste_btn)
    widgets["paste_handler"] = paste_handler

    save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(w - 240, btn_y, 100, 32))
    save_btn.setTitle_(S.BTN_SAVE)
    save_btn.setBezelStyle_(NSBezelStyleRounded)
    save_btn.setFont_(NSFont.boldSystemFontOfSize_(13))
    save_handler = FormHandler.alloc().initWithAction_(on_save)
    save_btn.setTarget_(save_handler)
    save_btn.setAction_("performAction:")
    content.addSubview_(save_btn)
    widgets["save_handler"] = save_handler

    cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(w - 130, btn_y, 100, 32))
    cancel_btn.setTitle_(S.BTN_CANCEL)
    cancel_btn.setBezelStyle_(NSBezelStyleRounded)
    cancel_btn.setFont_(NSFont.systemFontOfSize_(12))
    cancel_handler = FormHandler.alloc().initWithAction_(on_cancel)
    cancel_btn.setTarget_(cancel_handler)
    cancel_btn.setAction_("performAction:")
    content.addSubview_(cancel_btn)
    widgets["cancel_handler"] = cancel_handler

    return widgets


def main(as_child=False):
    print(f"[DEBUG] add_event_window.main(as_child={as_child})", flush=True)
    app = NSApplication.sharedApplication()

    original_policy = app.activationPolicy()
    try:
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    except Exception as e:
        print(f"[DEBUG] setActivationPolicy(Regular) failed: {e}", flush=True)
    _safe_activate(app)

    pb = NSPasteboard.generalPasteboard()
    clipboard_text = pb.stringForType_("public.utf8-plain-text") or ""
    parsed = parse_clipboard(clipboard_text)

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, _WINDOW_W, _WINDOW_H),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable,
        NSBackingStoreBuffered,
        False,
    )
    panel.setTitle_(S.ADD_EVENT_TITLE)
    panel.center()
    panel.setReleasedWhenClosed_(False)
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    panel.setHidesOnDeactivate_(False)

    effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, _WINDOW_W, _WINDOW_H))
    effect.setMaterial_(NSVisualEffectMaterialSidebar)
    effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    effect.setState_(NSVisualEffectStateActive)
    effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

    tab_view = NSTabView.alloc().initWithFrame_(NSMakeRect(
        _TAB_PADDING, _TAB_PADDING,
        _WINDOW_W - 2 * _TAB_PADDING,
        _WINDOW_H - 2 * _TAB_PADDING - 24,
    ))
    tab_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

    tab_content_w = _WINDOW_W - 2 * _TAB_PADDING
    tab_content_h = _WINDOW_H - 2 * _TAB_PADDING - 40
    tab_content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, tab_content_w, tab_content_h))
    tab_content.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

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
        widgets["title"].setStringValue_(p["title"])
        widgets["location"].setStringValue_(p["video_url"])
        widgets["url"].setStringValue_(p["url"])
        widgets["notes"].setString_(p["notes"])

    def save_action():
        ev_title = widgets["title"].stringValue()
        ev_meeting = widgets["location"].stringValue()
        ev_tracker = widgets["url"].stringValue()
        ev_notes = widgets["notes"].string()
        ev_start = widgets["start"].dateValue()
        try:
            ev_dur_min = float(widgets["duration"].stringValue() or 30)
        except ValueError:
            ev_dur_min = 30

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
            close_panel()
        else:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(S.ADD_EVENT_ERR_TITLE)
            alert.setInformativeText_(S.ADD_EVENT_ERR_BODY.format(error=error))
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

    widgets = _build_event_tab(
        tab_content, parsed, tab_content_w, tab_content_h,
        save_action, cancel_action, paste_from_clipboard,
    )

    item = NSTabViewItem.alloc().initWithIdentifier_("event")
    item.setLabel_("Event")
    item.setView_(tab_content)
    tab_view.addTabViewItem_(item)

    effect.addSubview_(tab_view)
    panel.setContentView_(effect)

    _RETAINED_HANDLERS[id(panel)] = {
        "paste": widgets["paste_handler"],
        "save": widgets["save_handler"],
        "cancel": widgets["cancel_handler"],
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
