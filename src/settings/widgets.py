# src/settings/widgets.py
"""Фабрики контролов AppKit с единым стилем."""

from collections.abc import Callable

import objc
from AppKit import (
    NSBezelBorder,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSPopUpButton,
    NSScrollView,
    NSStepper,
    NSTableColumn,
    NSTableView,
    NSTextField,
)
from Foundation import NSObject


class _Handler(NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(_Handler, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def fire_(self, sender):
        try:
            self._callback(sender)
        except Exception as e:
            print(f"[SETTINGS] handler error: {e}", flush=True)


class _ListDataSource(NSObject):
    """Один класс на модуль — иначе pyobjc ругается при втором вызове."""

    def initWithItems_(self, items_):
        self = objc.super(_ListDataSource, self).init()
        if self is None:
            return None
        self.items = items_
        return self

    def numberOfRowsInTableView_(self, table):
        return len(self.items)

    def tableView_objectValueForTableColumn_row_(self, table, col, row):
        if 0 <= row < len(self.items):
            return self.items[row]
        return ""


def _retain(widget, handler, callbacks):
    """Держим handler живым — иначе target умрёт и клики пропадут."""
    callbacks.append(handler)


def _frame(f):
    """Принимает tuple(x,y,w,h) или NSRect; возвращает NSRect для AppKit."""
    if isinstance(f, tuple) and len(f) == 4:
        return NSMakeRect(f[0], f[1], f[2], f[3])
    return f


def make_label(text, frame, bold=False, secondary=True, size=12):
    f = NSTextField.alloc().initWithFrame_(_frame(frame))
    f.setStringValue_(text)
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(False)
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    f.setTextColor_(NSColor.secondaryLabelColor() if secondary else NSColor.labelColor())
    f.setLineBreakMode_(NSLineBreakByTruncatingTail)
    return f


def make_checkbox(text, frame, initial, on_toggle: Callable[[bool], None], callbacks):
    btn = NSButton.alloc().initWithFrame_(_frame(frame))
    btn.setButtonType_(1)  # NSSwitchButton
    btn.setTitle_(text)
    btn.setFont_(NSFont.systemFontOfSize_(13))
    btn.setState_(1 if initial else 0)
    handler = _Handler.alloc().initWithCallback_(lambda s: on_toggle(bool(s.state())))
    btn.setTarget_(handler)
    btn.setAction_("fire:")
    _retain(btn, handler, callbacks)
    return btn


def make_popup(items, frame, current, on_change: Callable[[int], None], callbacks):
    """items — list[str]. on_change(index)."""
    popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(_frame(frame), False)
    for s in items:
        popup.addItemWithTitle_(s)
    if current in items:
        popup.selectItemWithTitle_(current)
    handler = _Handler.alloc().initWithCallback_(lambda s: on_change(s.indexOfSelectedItem()))
    popup.setTarget_(handler)
    popup.setAction_("fire:")
    _retain(popup, handler, callbacks)
    return popup


def make_textfield(frame, initial, on_change: Callable[[str], None], callbacks):
    tf = NSTextField.alloc().initWithFrame_(_frame(frame))
    tf.setStringValue_(initial)
    tf.setFont_(NSFont.systemFontOfSize_(13))
    handler = _Handler.alloc().initWithCallback_(lambda s: on_change(s.stringValue()))
    tf.setTarget_(handler)
    tf.setAction_("fire:")
    _retain(tf, handler, callbacks)
    return tf


def make_stepper(frame, initial, min_val, max_val, on_change: Callable[[int], None], callbacks):
    st = NSStepper.alloc().initWithFrame_(_frame(frame))
    st.setMinValue_(min_val)
    st.setMaxValue_(max_val)
    st.setIntValue_(initial)
    st.setIncrement_(1)
    st.setValueWraps_(False)
    handler = _Handler.alloc().initWithCallback_(lambda s: on_change(int(s.intValue())))
    st.setTarget_(handler)
    st.setAction_("fire:")
    _retain(st, handler, callbacks)
    return st


def make_button(title, frame, on_click: Callable[[], None], callbacks, bold=False):
    btn = NSButton.alloc().initWithFrame_(_frame(frame))
    btn.setTitle_(title)
    btn.setBezelStyle_(NSBezelStyleRounded)
    btn.setFont_(NSFont.boldSystemFontOfSize_(13) if bold else NSFont.systemFontOfSize_(13))
    handler = _Handler.alloc().initWithCallback_(lambda s: on_click())
    btn.setTarget_(handler)
    btn.setAction_("fire:")
    _retain(btn, handler, callbacks)
    return btn


def make_spacer(width, height=1):
    return NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))


def make_listbox(frame, items, callbacks):
    """NSScrollView + NSTableView на одну колонку, без header.

    Возвращает (scroll_view, table_view, data_source).
    data_source.items — список строк, меняй на месте и зови table_view.reloadData().
    """
    rect = _frame(frame)
    scroll = NSScrollView.alloc().initWithFrame_(rect)
    scroll.setHasVerticalScroller_(True)
    scroll.setBorderType_(NSBezelBorder)

    table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, rect.size.width, rect.size.height))
    table.setUsesAlternatingRowBackgroundColors_(True)
    table.setAllowsMultipleSelection_(False)
    table.setRowHeight_(22)

    col = NSTableColumn.alloc().initWithIdentifier_("domain")
    col.setTitle_("Domain")
    col.setWidth_(rect.size.width - 20)
    table.addTableColumn_(col)
    table.setHeaderView_(None)

    ds = _ListDataSource.alloc().initWithItems_(list(items))
    table.setDataSource_(ds)
    table.setDelegate_(ds)
    scroll.setDocumentView_(table)

    callbacks.append(ds)
    return scroll, table, ds
