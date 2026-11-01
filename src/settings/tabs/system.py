# src/settings/tabs/system.py
"""Вкладка System: hotkey, DND, Clear History, Export/Import, Reset, Open log, Restart."""

import json
import subprocess
import sys

from AppKit import (
    NSAlert,
    NSApplication,
    NSMakeRect,
    NSOpenPanel,
    NSSavePanel,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
)

from config import CONFIG, DEFAULT_CONFIG, save_config

from ..rows import RowLayout, row_with_label
from ..widgets import make_button, make_checkbox, make_label


class SystemTab:
    def __init__(self, binding, reload_callback=None):
        self.binding = binding
        self.reload_callback = reload_callback
        self._callbacks = []
        self._view = None
        self._dnd_btn = None
        self._hotkey_status_lbl = None

    def view(self):
        if self._view is not None:
            return self._view

        w, h = 700, 480
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        v.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        layout = RowLayout(x=20, y_top=h - 20, width=w - 40)

        # ----- Hotkey -----
        row_with_label(v, layout, "Hotkey Cmd+Ctrl+N")
        y = layout.y + layout.row_gap
        self._hotkey_status_lbl = make_label(
            "", NSMakeRect(layout.control_x, y + 6, 280, 18), secondary=False, size=12
        )
        v.addSubview_(self._hotkey_status_lbl)

        ax_btn = make_button(
            "Open Accessibility Settings…",
            NSMakeRect(layout.control_x + 270, y, 200, 26),
            self._open_accessibility,
            self._callbacks,
        )
        v.addSubview_(ax_btn)
        self._refresh_hotkey_status()
        layout.y -= 20

        # ----- DND -----
        row_with_label(v, layout, "Do Not Disturb")
        y = layout.y + layout.row_gap
        self._dnd_btn = make_button(
            "", NSMakeRect(layout.control_x, y, 300, 26), self._toggle_dnd, self._callbacks
        )
        v.addSubview_(self._dnd_btn)
        self._refresh_dnd_state()

        # ----- Include notes in copy -----
        row_with_label(v, layout, "Include Notes in Copy")
        y = layout.y + layout.row_gap
        cb = make_checkbox(
            "Копировать notes в буфер обмена",
            NSMakeRect(layout.control_x, y, 300, 22),
            bool(CONFIG.get("include_notes_in_copy", False)),
            lambda val: self.binding.set("include_notes_in_copy", bool(val)),
            self._callbacks,
        )
        v.addSubview_(cb)

        # ----- Clear History -----
        row_with_label(v, layout, "Clear History")
        y = layout.y + layout.row_gap
        clear_btn = make_button(
            "Очистить историю уведомлений",
            NSMakeRect(layout.control_x, y, 300, 26),
            self._clear_history,
            self._callbacks,
        )
        v.addSubview_(clear_btn)

        # ----- Export / Import / Reset -----
        row_with_label(v, layout, "Config")
        y = layout.y + layout.row_gap
        export_btn = make_button(
            "Export…", NSMakeRect(layout.control_x, y, 130, 26), self._export_config, self._callbacks
        )
        v.addSubview_(export_btn)
        import_btn = make_button(
            "Import…",
            NSMakeRect(layout.control_x + 138, y, 130, 26),
            self._import_config,
            self._callbacks,
        )
        v.addSubview_(import_btn)
        reset_btn = make_button(
            "Reset to defaults",
            NSMakeRect(layout.control_x + 276, y, 160, 26),
            self._reset_defaults,
            self._callbacks,
        )
        v.addSubview_(reset_btn)

        # ----- Open log / Restart -----
        row_with_label(v, layout, "Diagnostics")
        y = layout.y + layout.row_gap
        open_log_btn = make_button(
            "Open log", NSMakeRect(layout.control_x, y, 130, 26), self._open_log, self._callbacks
        )
        v.addSubview_(open_log_btn)
        restart_btn = make_button(
            "Restart NotifyMe",
            NSMakeRect(layout.control_x + 138, y, 160, 26),
            self._restart_app,
            self._callbacks,
        )
        v.addSubview_(restart_btn)

        hint = make_label(
            "Изменения сохраняются автоматически. Hotkey применяется после Relaunch (Restart).",
            NSMakeRect(layout.x, 16, layout.width, 16),
            secondary=True,
            size=11,
        )
        v.addSubview_(hint)

        self._view = v
        return v

    # ----- hotkey -----

    def _refresh_hotkey_status(self):
        if self._hotkey_status_lbl is None:
            return
        try:
            from hotkeys import is_accessibility_granted
            granted = is_accessibility_granted()
        except Exception:
            granted = False
        self._hotkey_status_lbl.setStringValue_(
            "✓ Accessibility granted" if granted else "Needs Accessibility"
        )

    def _open_accessibility(self):
        try:
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ])
        except Exception as e:
            print(f"[SETTINGS] open Accessibility failed: {e}", flush=True)

    # ----- DND -----

    def _refresh_dnd_state(self):
        if self._dnd_btn is None:
            return
        v = CONFIG.get("dnd_until")
        if v:
            self._dnd_btn.setTitle_(f"🔕 DND active until {v[11:16] if len(v) > 16 else v}")
        else:
            self._dnd_btn.setTitle_("🔔 Enable DND until current event ends")

    def _toggle_dnd(self):
        from datetime import datetime as dt
        from datetime import timedelta

        from calendar_service import get_upcoming_events, request_calendar_access
        from config import save_config as _save

        current = CONFIG.get("dnd_until")
        if current:
            CONFIG["dnd_until"] = None
            _save(CONFIG)
            print("[SETTINGS] DND disabled", flush=True)
            self._refresh_dnd_state()
            return

        try:
            store = request_calendar_access()
        except Exception as e:
            print(f"[SETTINGS] request_calendar_access failed: {e}", flush=True)
            return

        now = dt.now()
        events = get_upcoming_events(store)
        ongoing = [ev for ev in events if ev["start"] <= now <= ev["end"]]
        if not ongoing:
            print("[SETTINGS] DND: no ongoing event", flush=True)
            return
        latest_end = max(ev["end"] for ev in ongoing) + timedelta(seconds=1)
        CONFIG["dnd_until"] = latest_end.isoformat()
        _save(CONFIG)
        print(f"[SETTINGS] DND until {latest_end}", flush=True)
        self._refresh_dnd_state()

    # ----- Clear History -----

    def _clear_history(self):
        try:
            from alarm_utils import close_all_alarms
            close_all_alarms()
        except Exception as e:
            print(f"[SETTINGS] close_all_alarms failed: {e}", flush=True)
        try:
            from state_manager import load_state, save_state
            ids = load_state()
            ids.clear()
            save_state(ids)
        except Exception as e:
            print(f"[SETTINGS] clear state failed: {e}", flush=True)
        print("[SETTINGS] history cleared", flush=True)

    # ----- Export / Import / Reset -----

    def _export_config(self):
        panel = NSSavePanel.savePanel()
        panel.setTitle_("Export NotifyMe config")
        panel.setNameFieldStringValue_("notifyme-config.json")
        panel.setAllowedFileTypes_(["json"])
        if panel.runModal() != 1:
            return
        path = panel.URL().path()
        try:
            with open(path, "w") as f:
                json.dump(CONFIG, f, indent=4, ensure_ascii=False)
            print(f"[SETTINGS] exported to {path}", flush=True)
        except Exception as e:
            print(f"[SETTINGS] export failed: {e}", flush=True)

    def _import_config(self):
        panel = NSOpenPanel.openPanel()
        panel.setTitle_("Import NotifyMe config")
        panel.setAllowedFileTypes_(["json"])
        panel.setAllowsMultipleSelection_(False)
        if panel.runModal() != 1:
            return
        path = panel.URL().path()
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            self._alert("Import failed", f"Cannot read file:\n{e}")
            return
        if not isinstance(data, dict):
            self._alert("Import failed", "File is not a JSON object")
            return

        CONFIG.clear()
        CONFIG.update(DEFAULT_CONFIG)
        CONFIG.update(data)
        save_config(CONFIG)
        print(f"[SETTINGS] imported from {path}", flush=True)
        self._alert("Import OK", "Config imported. Settings window will reload.")
        if self.reload_callback:
            self.reload_callback()
        else:
            self._refresh_dnd_state()
            self._refresh_hotkey_status()

    def _reset_defaults(self):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Reset to defaults?")
        alert.setInformativeText_("All settings in ~/.notifyme/config.json will be reset.")
        alert.addButtonWithTitle_("Reset")
        alert.addButtonWithTitle_("Cancel")
        alert.setAlertStyle_(1)
        if alert.runModal() != 1000:
            return
        CONFIG.clear()
        CONFIG.update(DEFAULT_CONFIG)
        save_config(CONFIG)
        print("[SETTINGS] reset to defaults", flush=True)
        if self.reload_callback:
            self.reload_callback()
        else:
            self._refresh_dnd_state()
            self._refresh_hotkey_status()

    # ----- Diagnostics -----

    def _open_log(self):
        try:
            subprocess.Popen(["open", "/tmp/notifyme_debug.log"])
        except Exception as e:
            print(f"[SETTINGS] open log failed: {e}", flush=True)

    def _restart_app(self):
        try:
            print("[SETTINGS] restart requested", flush=True)
            exe = sys.executable
            argv = [exe] + list(sys.argv)
            subprocess.Popen(argv)
            NSApplication.sharedApplication().terminate_(None)
        except Exception as e:
            print(f"[SETTINGS] restart failed: {e}", flush=True)

    # ----- utils -----

    def _alert(self, title, message):
        a = NSAlert.alloc().init()
        a.setMessageText_(title)
        a.setInformativeText_(message)
        a.addButtonWithTitle_("OK")
        a.runModal()
