# src/settings/tabs/conferences.py
"""Вкладка Conferences: домены tracker/meeting + Add known + undo."""

from AppKit import (
    NSMakeRect,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
)

from config import CONFIG
from config.domains import KNOWN_MEETING_DOMAINS, KNOWN_TRACKER_DOMAINS

from ..rows import RowLayout, row_with_label
from ..widgets import (
    _Handler,
    _retain,
    make_button,
    make_label,
    make_listbox,
    make_textfield,
)

_MAX_UNDO = 10


class ConferencesTab:
    def __init__(self, binding):
        self.binding = binding
        self._callbacks = []
        self._view = None
        self._undo: list[tuple[str, str, str]] = []  # (action, key, value)
        self._tracker_items: list[str] = list(CONFIG.get("custom_tracker_domains", []) or [])
        self._meeting_items: list[str] = list(CONFIG.get("custom_meeting_domains", []) or [])
        self._tracker_table = None
        self._tracker_ds = None
        self._meeting_table = None
        self._meeting_ds = None
        self._undo_btn = None

        # Первичный автозаполнение: если пусто, заливаем known-домены и сохраняем в CONFIG.
        if not self._tracker_items:
            self._tracker_items = list(KNOWN_TRACKER_DOMAINS)
            self.binding.set("custom_tracker_domains", list(self._tracker_items))
        if not self._meeting_items:
            self._meeting_items = list(KNOWN_MEETING_DOMAINS)
            self.binding.set("custom_meeting_domains", list(self._meeting_items))

    def view(self):
        if self._view is not None:
            return self._view

        w, h = 700, 480
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        v.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        layout = RowLayout(x=20, y_top=h - 20, width=w - 40)

        # ----- Tracker domains -----
        row_with_label(v, layout, "Tracker domains")
        y = layout.y + layout.row_gap
        scroll_t, table_t, ds_t = make_listbox(
            NSMakeRect(layout.control_x, y - 110, layout.control_w, 120),
            self._tracker_items,
            self._callbacks,
        )
        scroll_t.setAutoresizingMask_(NSViewWidthSizable)
        v.addSubview_(scroll_t)
        self._tracker_table = table_t
        self._tracker_ds = ds_t
        layout.y = y - 110 - layout.row_gap

        y = layout.next_y()
        self._add_row_for_list(
            v, layout, y,
            placeholder="example: jira.company.com",
            on_add=lambda text: self._add_domain("custom_tracker_domains", text, "tracker"),
            on_remove=lambda: self._remove_selected("custom_tracker_domains", "tracker"),
            on_reset=lambda: self._reset_to_known("custom_tracker_domains", KNOWN_TRACKER_DOMAINS, "tracker"),
        )

        # ----- Meeting domains -----
        layout.y -= 30
        row_with_label(v, layout, "Meeting domains")
        y = layout.y + layout.row_gap
        scroll_m, table_m, ds_m = make_listbox(
            NSMakeRect(layout.control_x, y - 110, layout.control_w, 120),
            self._meeting_items,
            self._callbacks,
        )
        scroll_m.setAutoresizingMask_(NSViewWidthSizable)
        v.addSubview_(scroll_m)
        self._meeting_table = table_m
        self._meeting_ds = ds_m
        layout.y = y - 110 - layout.row_gap

        y = layout.next_y()
        self._add_row_for_list(
            v, layout, y,
            placeholder="example: meet.company.com",
            on_add=lambda text: self._add_domain("custom_meeting_domains", text, "meeting"),
            on_remove=lambda: self._remove_selected("custom_meeting_domains", "meeting"),
            on_reset=lambda: self._reset_to_known("custom_meeting_domains", KNOWN_MEETING_DOMAINS, "meeting"),
        )

        # ----- Undo -----
        y_undo = 60
        self._undo_btn = make_button(
            "↶ Undo",
            NSMakeRect(layout.control_x, y_undo, 100, 26),
            self._undo_last,
            self._callbacks,
        )
        self._undo_btn.setEnabled_(False)
        v.addSubview_(self._undo_btn)

        hint = make_label(
            "Домены без http://. Известные подставлены по умолчанию, их можно удалять и пополнять.",
            NSMakeRect(layout.x, y_undo - 30, layout.width, 18),
            secondary=True,
            size=11,
        )
        v.addSubview_(hint)

        self._view = v
        return v

    def _add_row_for_list(self, content, layout, y, placeholder, on_add, on_remove, on_reset):
        field_w = layout.control_w - 360
        field = make_textfield(
            NSMakeRect(layout.control_x, y, field_w, 26),
            "",
            lambda text: None,
            self._callbacks,
        )
        try:
            field.setPlaceholderString_(placeholder)
        except Exception:
            try:
                field.cell().setPlaceholderString_(placeholder)
            except Exception:
                pass
        content.addSubview_(field)

        def on_enter(_sender):
            on_add(field.stringValue())
            field.setStringValue_("")

        enter_handler = _Handler.alloc().initWithCallback_(on_enter)
        field.setTarget_(enter_handler)
        field.setAction_("fire:")
        _retain(field, enter_handler, self._callbacks)

        add_btn = make_button(
            "+",
            NSMakeRect(layout.control_x + field_w + 8, y, 32, 26),
            lambda: (on_add(field.stringValue()), field.setStringValue_("")),
            self._callbacks,
            bold=True,
        )
        content.addSubview_(add_btn)

        remove_btn = make_button(
            "−",
            NSMakeRect(layout.control_x + field_w + 44, y, 32, 26),
            on_remove,
            self._callbacks,
            bold=True,
        )
        content.addSubview_(remove_btn)

        reset_btn = make_button(
            "Reset to known",
            NSMakeRect(layout.control_x + field_w + 84, y, 140, 26),
            on_reset,
            self._callbacks,
        )
        content.addSubview_(reset_btn)

    # ----- действия -----

    def _add_domain(self, key, raw, kind):
        domain = (raw or "").strip().lower()
        if not domain:
            return
        for prefix in ("https://", "http://"):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.split("/", 1)[0].strip()
        if not domain or " " in domain:
            print(f"[SETTINGS] invalid domain: {raw!r}", flush=True)
            return
        items = self._items_for(key)
        if domain in items:
            print(f"[SETTINGS] {kind} domain already present: {domain!r}", flush=True)
            return
        items.append(domain)
        self._push_undo("add", key, domain)
        self._apply(key, items)
        print(f"[SETTINGS] added {kind} domain: {domain!r}", flush=True)

    def _remove_selected(self, key, kind):
        table = self._table_for(kind)
        if table is None:
            return
        row = int(table.selectedRow())
        items = self._items_for(key)
        if row < 0 or row >= len(items):
            return
        removed = items.pop(row)
        self._push_undo("remove", key, removed)
        self._apply(key, items)
        print(f"[SETTINGS] removed {kind} domain: {removed!r}", flush=True)

    def _reset_to_known(self, key, known_list, kind):
        items = self._items_for(key)
        added = 0
        for d in known_list:
            d = d.strip().lower()
            if not d or d in items:
                continue
            items.append(d)
            self._push_undo("add", key, d)
            added += 1
        if added:
            self._apply(key, items)
        print(f"[SETTINGS] reset {kind}: +{added} known", flush=True)

    def _undo_last(self):
        if not self._undo:
            return
        action, key, value = self._undo.pop()
        items = self._items_for(key)
        if action == "add":
            if value in items:
                items.remove(value)
        elif action == "remove" and value not in items:
            items.append(value)
        self._apply(key, items)
        if not self._undo and self._undo_btn is not None:
            try:
                self._undo_btn.setEnabled_(False)
            except Exception:
                pass
        print(f"[SETTINGS] undo {action} {key}: {value!r}", flush=True)

    def _push_undo(self, action, key, value):
        self._undo.append((action, key, value))
        if len(self._undo) > _MAX_UNDO:
            self._undo.pop(0)
        if self._undo_btn is not None:
            try:
                self._undo_btn.setEnabled_(True)
            except Exception:
                pass

    def _apply(self, key, items):
        self.binding.set(key, list(items))
        kind = "tracker" if key == "custom_tracker_domains" else "meeting"
        table = self._table_for(kind)
        ds = self._ds_for(kind)
        if ds is not None:
            ds.items = list(items)
        if table is not None:
            try:
                table.reloadData()
            except Exception as e:
                print(f"[SETTINGS] reloadData failed: {e}", flush=True)

    # ----- утилиты -----

    def _items_for(self, key):
        if key == "custom_tracker_domains":
            return self._tracker_items
        return self._meeting_items

    def _table_for(self, kind):
        return self._tracker_table if kind == "tracker" else self._meeting_table

    def _ds_for(self, kind):
        return self._tracker_ds if kind == "tracker" else self._meeting_ds
