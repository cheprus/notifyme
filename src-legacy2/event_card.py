# src/event_card.py
import subprocess
from datetime import datetime
from typing import Any

import objc
from AppKit import (
    NSApplicationActivationPolicyRegular,
    NSApplicationDidResignActiveNotification,
    NSBackingStoreBuffered,
    NSBezelBorder,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSPanel,
    NSPasteboard,
    NSScreenSaverWindowLevel,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowDidResignKeyNotification,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSApplication, NSNotificationCenter, NSObject

from ui_utils import (
    format_event_datetime,
    format_event_datetime_for_copy,
    get_event_color,
    to_display_tz,
)

# Ключ — id(panel)
_RETAINED_PANELS: dict[int, Any] = {}
_RETAINED_HANDLERS: dict[int, Any] = {}

_GRACE_SECONDS = 0.5


class CardHandler(NSObject):
    def initWithAction_(self, action):
        self = objc.super(CardHandler, self).init()
        if self is None:
            return None
        self.action = action
        return self

    def performAction_(self, sender):
        self.action()


def _close_card(panel_id):
    state = _RETAINED_HANDLERS.pop(panel_id, None)
    if state:
        cleanup = state.get("cleanup_observers")
        if cleanup:
            try:
                cleanup()
            except Exception:
                pass
    panel = _RETAINED_PANELS.pop(panel_id, None)
    if panel:
        try:
            panel.orderOut_(None)
            panel.close()
        except Exception:
            pass


def close_all_cards():
    for pid in list(_RETAINED_PANELS.keys()):
        _close_card(pid)


def _make_button(title, frame, handler, bold=False):
    btn = NSButton.alloc().initWithFrame_(frame)
    btn.setTitle_(title)
    btn.setBezelStyle_(NSBezelStyleRounded)
    btn.setFont_(NSFont.systemFontOfSize_(13) if not bold else NSFont.boldSystemFontOfSize_(13))
    btn.setTarget_(handler)
    btn.setAction_("performAction:")
    return btn


def _label(text, frame, bold=False, secondary=False, size=13):
    f = NSTextField.alloc().initWithFrame_(frame)
    f.setStringValue_(text)
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(not secondary)
    if bold:
        f.setFont_(NSFont.boldSystemFontOfSize_(size))
    else:
        f.setFont_(NSFont.systemFontOfSize_(size))
    if secondary:
        f.setTextColor_(NSColor.secondaryLabelColor())
    else:
        f.setTextColor_(NSColor.labelColor())
    f.setLineBreakMode_(NSLineBreakByTruncatingTail)
    return f


def _open_url(url):
    try:
        subprocess.Popen(["open", url])
    except Exception as e:
        print(f"[DEBUG] open failed: {e}", flush=True)


def show_event_card(event):
    close_all_cards()

    app = NSApplication.sharedApplication()
    original_policy = app.activationPolicy()
    try:
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    except Exception:
        pass
    try:
        app.activateIgnoringOtherApps_(True)
    except Exception:
        try:
            app.activate()
        except Exception:
            pass

    now = datetime.now()
    title = (event.get("title") or "Untitled").strip()
    start = event.get("start")
    end = event.get("end")
    location = event.get("location") or ""
    url = event.get("url") or ""
    calendar = (event.get("calendar_title") or "").strip()
    notes = (event.get("notes") or "").strip()

    event_color = get_event_color(event, now)

    padding = 20
    width = 540
    row_h = 24

    base_rows = 1
    if calendar: base_rows += 1
    if start: base_rows += 1
    if end: base_rows += 1
    if location: base_rows += 1
    if url: base_rows += 1

    notes_h = 90 if notes else 0
    height = padding * 2 + base_rows * row_h + (notes_h + 20 if notes else 0) + 44

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
        NSBackingStoreBuffered,
        False
    )
    panel.setTitle_(f"Event — {calendar}" if calendar else "Event")
    panel.setLevel_(NSScreenSaverWindowLevel)
    panel.center()
    panel.setReleasedWhenClosed_(False)
    panel.setHidesOnDeactivate_(True)
    panel.setFloatingPanel_(True)
    panel.setTitleVisibility_(1)
    panel.setTitlebarAppearsTransparent_(True)
    panel.setAlphaValue_(1.0)

    effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    effect.setMaterial_(NSVisualEffectMaterialHUDWindow)
    effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    effect.setState_(NSVisualEffectStateActive)
    effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    panel.setContentView_(effect)
    content = effect

    y = height - padding
    label_w = 100
    field_x = padding + label_w + 10
    field_w = width - field_x - padding

    def add_row(label_text, value_text, secondary=False, bold=False):
        nonlocal y
        lbl = _label(label_text, NSMakeRect(padding, y - 18, label_w, 18), secondary=True, size=12)
        content.addSubview_(lbl)
        val = _label(value_text, NSMakeRect(field_x, y - 18, field_w, 18), secondary=secondary, bold=bold)
        content.addSubview_(val)
        y -= row_h

    def add_calendar_row(cal_name):
        nonlocal y
        lbl = _label("Calendar", NSMakeRect(padding, y - 18, label_w, 18), secondary=True, size=12)
        content.addSubview_(lbl)
        dot = NSView.alloc().initWithFrame_(NSMakeRect(field_x, y - 16, 10, 10))
        dot.setWantsLayer_(True)
        if dot.layer() is not None:
            dot.layer().setBackgroundColor_(event_color.CGColor())
            dot.layer().setCornerRadius_(5.0)
        content.addSubview_(dot)
        val = _label(cal_name, NSMakeRect(field_x + 16, y - 18, field_w - 16, 18), secondary=False)
        content.addSubview_(val)
        y -= row_h

    add_row("Title", title, secondary=False, bold=True)
    if calendar:
        add_calendar_row(calendar)
    if start:
        add_row("Start", format_event_datetime(start, now), secondary=False)
    if end:
        add_row("End", to_display_tz(end).strftime("%H:%M"), secondary=False)
    if location:
        add_row("Location", location, secondary=True)
    if url:
        add_row("URL", url, secondary=True)

    if notes:
        y -= 10
        lbl = _label("Notes", NSMakeRect(padding, y - 18, label_w, 18), secondary=True, size=12)
        content.addSubview_(lbl)
        scroll_view = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(field_x, y - notes_h, field_w, notes_h)
        )
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setBorderType_(NSBezelBorder)
        text_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, field_w, notes_h)
        )
        text_view.setEditable_(False)
        text_view.setSelectable_(True)
        text_view.setFont_(NSFont.systemFontOfSize_(12))
        text_view.setString_(notes)
        scroll_view.setDocumentView_(text_view)
        content.addSubview_(scroll_view)
        y -= (notes_h + 10)

    btn_y = padding
    btn_h = 32
    gap = 10
    right_x = width - padding

    panel_id = id(panel)
    shown_at = {"t": datetime.now()}
    observers_holder: dict[str, list[Any]] = {"items": []}
    close_guard = {"closed": False}

    def cleanup_observers():
        nc = NSNotificationCenter.defaultCenter()
        for obs in observers_holder["items"]:
            try:
                nc.removeObserver_(obs)
            except Exception:
                pass
        observers_holder["items"] = []

    def restore_policy():
        try:
            app.setActivationPolicy_(original_policy)
        except Exception:
            pass

    def close_action():
        if close_guard["closed"]:
            return
        close_guard["closed"] = True
        cleanup_observers()
        _close_card(panel_id)
        restore_policy()

    handlers = {"cleanup_observers": cleanup_observers}

    close_w = 100
    right_x -= close_w
    h_close = CardHandler.alloc().initWithAction_(close_action)
    btn_close = _make_button("Закрыть", NSMakeRect(right_x, btn_y, close_w, btn_h), h_close, bold=True)
    content.addSubview_(btn_close)
    handlers["close"] = h_close
    right_x -= gap

    copy_w = 130
    right_x -= copy_w

    def copy_action():
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        text = f"📅 Event: {title}\n"
        if start:
            text += f"{format_event_datetime_for_copy(start, now)}\n"
        if url:
            text += f"🔗 {url}\n"
        if location:
            text += f"📍 {location}\n"
        pb.setString_forType_(text, "public.utf8-plain-text")
        close_action()

    h_copy = CardHandler.alloc().initWithAction_(copy_action)
    btn_copy = _make_button("Копировать", NSMakeRect(right_x, btn_y, copy_w, btn_h), h_copy)
    content.addSubview_(btn_copy)
    handlers["copy"] = h_copy
    right_x -= gap

    if location:
        open_w = 150
        right_x -= open_w
        def open_location_action(loc=location):
            _open_url(loc)
            close_action()
        h_loc = CardHandler.alloc().initWithAction_(open_location_action)
        btn_loc = _make_button("Открыть встречу", NSMakeRect(right_x, btn_y, open_w, btn_h), h_loc, bold=True)
        content.addSubview_(btn_loc)
        handlers["open_location"] = h_loc
    elif url:
        open_w = 150
        right_x -= open_w
        def open_url_action(u=url):
            _open_url(u)
            close_action()
        h_url = CardHandler.alloc().initWithAction_(open_url_action)
        btn_url = _make_button("Открыть трекер", NSMakeRect(right_x, btn_y, open_w, btn_h), h_url, bold=True)
        content.addSubview_(btn_url)
        handlers["open_url"] = h_url

    def on_app_resign(note):
        elapsed = (datetime.now() - shown_at["t"]).total_seconds()
        if elapsed >= _GRACE_SECONDS:
            close_action()
    obs_app = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
        NSApplicationDidResignActiveNotification, None, None, on_app_resign
    )
    observers_holder["items"].append(obs_app)

    def on_resign_key(note):
        elapsed = (datetime.now() - shown_at["t"]).total_seconds()
        if elapsed < _GRACE_SECONDS:
            return
        close_action()
    obs_key = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
        NSWindowDidResignKeyNotification, panel, None, on_resign_key
    )
    observers_holder["items"].append(obs_key)

    panel.makeKeyAndOrderFront_(None)
    panel.orderFrontRegardless()

    _RETAINED_PANELS[panel_id] = panel
    _RETAINED_HANDLERS[panel_id] = handlers
