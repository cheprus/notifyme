# src/settings/tabs/alarm.py
"""Вкладка Alarm: Notify Before/After, Snooze, Auto-close, Pulse, Sound, Output."""

import os
import subprocess

from AppKit import NSMakeRect, NSView

import audio_output
import strings as S
from config import (
    AUTO_CLOSE_PRESETS,
    AVAILABLE_SOUNDS,
    CONFIG,
    NOTIFY_AFTER_PRESETS,
    NOTIFY_BEFORE_PRESETS,
)
from menu_alarm import snooze_presets

from ..rows import RowLayout, add_helper, row_with_label
from ..widgets import make_button, make_label, make_popup

# Активные preview:
#   _PREVIEW_HANDLES — CoreAudio handle от play_on_device
#   _PREVIEW_PROCS   — subprocess.Popen для afplay-fallback
_PREVIEW_HANDLES: list = []
_PREVIEW_PROCS: list = []


def _stop_all_previews():
    """Безопасно остановить все preview, даже если handle от мёртвого устройства."""
    while _PREVIEW_HANDLES:
        h = _PREVIEW_HANDLES.pop()
        try:
            audio_output.stop_playing(h)
        except Exception as e:
            print(f"[SETTINGS] stop preview handle failed (device disconnected?): {e}", flush=True)
    while _PREVIEW_PROCS:
        p = _PREVIEW_PROCS.pop()
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass


class AlarmTab:
    """Контроллер одной вкладки. Интерфейс: view(), cleanup()."""

    def __init__(self, binding):
        self.binding = binding
        self._callbacks = []
        self._view = None
        self._widgets = {}
        self._output_popup = None
        self._output_values = []

    def cleanup(self):
        """Остановить все preview (вернуть системный default output)."""
        _stop_all_previews()

    def view(self):
        if self._view is not None:
            return self._view

        w, h = 700, 480
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))

        layout = RowLayout(x=20, y_top=h - 20, width=w - 40)

        self._build_notify(v, layout)
        self._build_snooze(v, layout)
        self._build_pulse(v, layout)
        self._build_sound(v, layout)
        self._build_output(v, layout)
        self._build_hint(v, layout)

        self._view = v
        return v

    # ----- секции -----

    def _build_notify(self, content, layout):
        row_with_label(content, layout, "Notify Before")
        presets = list(NOTIFY_BEFORE_PRESETS)
        current = int(CONFIG.get("notify_minutes_before", 5))
        labels = [self._minutes_label(m) for m in presets]
        if current not in presets:
            presets.append(current)
            labels.append(self._minutes_label(current) + " (custom)")
        y = layout.y + layout.row_gap
        popup = make_popup(
            labels,
            NSMakeRect(layout.control_x, y, 220, 26),
            self._minutes_label(current) + ("" if current in NOTIFY_BEFORE_PRESETS else " (custom)"),
            lambda idx: self.binding.set("notify_minutes_before", presets[idx]),
            self._callbacks,
        )
        content.addSubview_(popup)
        self._widgets["notify_minutes_before"] = (popup, presets, labels)

        row_with_label(content, layout, "Notify After (start)")
        presets_a = list(NOTIFY_AFTER_PRESETS)
        current_a = int(CONFIG.get("notify_minutes_after", 2))
        labels_a = [self._minutes_label(m) for m in presets_a]
        if current_a not in presets_a:
            presets_a.append(current_a)
            labels_a.append(self._minutes_label(current_a) + " (custom)")
        y = layout.y + layout.row_gap
        popup_a = make_popup(
            labels_a,
            NSMakeRect(layout.control_x, y, 220, 26),
            self._minutes_label(current_a) + ("" if current_a in NOTIFY_AFTER_PRESETS else " (custom)"),
            lambda idx: self.binding.set("notify_minutes_after", presets_a[idx]),
            self._callbacks,
        )
        content.addSubview_(popup_a)
        self._widgets["notify_minutes_after"] = (popup_a, presets_a, labels_a)

    def _build_snooze(self, content, layout):
        row_with_label(content, layout, "Snooze")
        notify_before = int(CONFIG.get("notify_minutes_before", 5))
        auto_close = int(CONFIG.get("auto_close_minutes", 15))
        current = int(CONFIG.get("snooze_minutes", 5))
        presets = [m for m in snooze_presets(notify_before) if m <= auto_close]
        if current not in presets and current <= auto_close:
            presets.append(current)
        if not presets:
            presets = [current]
        labels = [self._minutes_label(m) for m in presets]
        y = layout.y + layout.row_gap
        popup = make_popup(
            labels,
            NSMakeRect(layout.control_x, y, 220, 26),
            self._minutes_label(current) if current in presets else self._minutes_label(presets[0]),
            lambda idx: self.binding.set("snooze_minutes", presets[idx]),
            self._callbacks,
        )
        content.addSubview_(popup)
        self._widgets["snooze_minutes"] = (popup, presets, labels)

        row_with_label(content, layout, "Auto-close Alarm")
        presets_ac = list(AUTO_CLOSE_PRESETS)
        current_ac = int(CONFIG.get("auto_close_minutes", 15))
        labels_ac = [self._minutes_label(m) for m in presets_ac]
        if current_ac not in presets_ac:
            presets_ac.append(current_ac)
            labels_ac.append(self._minutes_label(current_ac) + " (custom)")
        y = layout.y + layout.row_gap
        popup_ac = make_popup(
            labels_ac,
            NSMakeRect(layout.control_x, y, 220, 26),
            self._minutes_label(current_ac) + ("" if current_ac in AUTO_CLOSE_PRESETS else " (custom)"),
            lambda idx: self.binding.set("auto_close_minutes", presets_ac[idx]),
            self._callbacks,
        )
        content.addSubview_(popup_ac)
        self._widgets["auto_close_minutes"] = (popup_ac, presets_ac, labels_ac)

    def _build_pulse(self, content, layout):
        on_secs = int(CONFIG.get("alarm_sound_on_seconds", 12))
        off_secs = int(CONFIG.get("alarm_sound_off_seconds", 60))

        row_with_label(content, layout, "Pulse ON (sec)")
        on_presets = [5, 10, 12, 15, 20, 30]
        on_labels = [f"{s} sec" for s in on_presets]
        if on_secs not in on_presets:
            on_presets.append(on_secs)
            on_labels.append(f"{on_secs} sec (custom)")
        y = layout.y + layout.row_gap
        popup_on = make_popup(
            on_labels,
            NSMakeRect(layout.control_x, y, 220, 26),
            f"{on_secs} sec" + ("" if on_secs in [5, 10, 12, 15, 20, 30] else " (custom)"),
            lambda idx: self.binding.set("alarm_sound_on_seconds", on_presets[idx]),
            self._callbacks,
        )
        content.addSubview_(popup_on)
        self._widgets["alarm_sound_on_seconds"] = (popup_on, on_presets, on_labels)

        row_with_label(content, layout, "Pulse OFF (sec)")
        off_presets = [15, 30, 60, 120, 300]
        off_labels = [f"{s} sec" for s in off_presets]
        if off_secs not in off_presets:
            off_presets.append(off_secs)
            off_labels.append(f"{off_secs} sec (custom)")
        y = layout.y + layout.row_gap
        popup_off = make_popup(
            off_labels,
            NSMakeRect(layout.control_x, y, 220, 26),
            f"{off_secs} sec" + ("" if off_secs in [15, 30, 60, 120, 300] else " (custom)"),
            lambda idx: self.binding.set("alarm_sound_off_seconds", off_presets[idx]),
            self._callbacks,
        )
        content.addSubview_(popup_off)
        self._widgets["alarm_sound_off_seconds"] = (popup_off, off_presets, off_labels)

    def _build_sound(self, content, layout):
        row_with_label(content, layout, "Sound")
        current = CONFIG.get("sound_file", "droid-meeting.mp3")
        current_base = os.path.basename(current)
        labels = list(AVAILABLE_SOUNDS)
        values = list(AVAILABLE_SOUNDS)
        idx = labels.index(current_base) if current_base in labels else 0
        y = layout.y + layout.row_gap

        def on_sound_change(i):
            _stop_all_previews()
            self.binding.set("sound_file", values[i])

        popup = make_popup(
            labels,
            NSMakeRect(layout.control_x, y, 300, 26),
            labels[idx],
            on_sound_change,
            self._callbacks,
        )
        content.addSubview_(popup)
        self._widgets["sound_file"] = (popup, values, labels)

        preview = make_button(
            "Preview",
            NSMakeRect(layout.control_x + 310, y, 100, 26),
            self._toggle_preview,
            self._callbacks,
        )
        content.addSubview_(preview)

    def _build_output(self, content, layout):
        row_with_label(content, layout, "Output")
        devices = self._list_outputs()
        current = CONFIG.get("sound_output_device", "Default")
        if current != "Default" and current not in devices:
            print(f"[SETTINGS] saved output device {current!r} not found, falling back to Default", flush=True)
            current = "Default"
            self.binding.set("sound_output_device", "Default")

        y = layout.y + layout.row_gap
        popup = make_popup(
            devices,
            NSMakeRect(layout.control_x, y, 280, 26),
            current,
            lambda i: self.binding.set("sound_output_device", devices[i]),
            self._callbacks,
        )
        content.addSubview_(popup)
        self._output_popup = popup
        self._output_values = list(devices)
        self._widgets["sound_output_device"] = (popup, devices, devices)

        refresh_btn = make_button(
            "↻",
            NSMakeRect(layout.control_x + 288, y, 30, 26),
            self._refresh_output_devices,
            self._callbacks,
        )
        content.addSubview_(refresh_btn)

        add_helper(
            content, layout, y - 4,
            "Default = системный выход. Другие — через временное переключение дефолта.",
            self._callbacks,
        )

    def _build_hint(self, content, layout):
        h = make_label(
            "Изменения сохраняются автоматически через 300 мс и применяются без перезапуска.",
            NSMakeRect(layout.x, 16, layout.width, 16),
            secondary=True,
            size=11,
        )
        content.addSubview_(h)

    # ----- утилиты -----

    def _minutes_label(self, m):
        if m == 0:
            return S.PRESET_AT_START
        if m % 60 == 0:
            return S.PRESET_HOUR.format(n=m // 60)
        return S.PRESET_MIN.format(n=m)

    def _list_outputs(self):
        devices = ["Default"]
        try:
            if audio_output.is_available():
                devices += [d["name"] for d in audio_output.list_output_devices()]
        except Exception as e:
            print(f"[SETTINGS] list_output_devices failed: {e}", flush=True)
        return devices

    def _refresh_output_devices(self):
        """Пересобрать список устройств. Останавливаем preview: handle от
        отключённого USB-устройства может ронять CoreAudio."""
        if self._output_popup is None:
            return

        # 1. Стоп всех preview ДО обновления списка — handle от мёртвого
        #    устройства нельзя оставлять в CoreAudio
        _stop_all_previews()

        devices = self._list_outputs()
        current = CONFIG.get("sound_output_device", "Default")
        if current not in devices:
            print(f"[SETTINGS] output {current!r} disconnected, resetting to Default", flush=True)
            current = "Default"
            self.binding.set("sound_output_device", "Default")

        try:
            self._output_popup.removeAllItems()
            for d in devices:
                self._output_popup.addItemWithTitle_(d)
            if current in devices:
                self._output_popup.selectItemWithTitle_(current)
        except Exception as e:
            print(f"[SETTINGS] refresh outputs failed: {e}", flush=True)
            return

        self._output_values = list(devices)
        self._widgets["sound_output_device"] = (self._output_popup, devices, devices)
        print(f"[SETTINGS] output devices refreshed: {devices}", flush=True)

    def _toggle_preview(self):
        """Если что-то играет — стоп. Иначе — запустить."""
        if _PREVIEW_HANDLES or _PREVIEW_PROCS:
            _stop_all_previews()
            print("[SETTINGS] preview stopped", flush=True)
            return
        self._start_preview()

    def _start_preview(self):
        from alarm_utils import _resolve_sound_path_for
        raw = CONFIG.get("sound_file", "")
        path = _resolve_sound_path_for(raw)
        if not path:
            print(f"[SETTINGS] sound not found: {raw}", flush=True)
            return
        device = CONFIG.get("sound_output_device", "Default")
        handle = audio_output.play_on_device(path, device, loops=0)
        if handle is not None:
            _PREVIEW_HANDLES.append(handle)
            print(f"[SETTINGS] preview on {device!r}: {raw}", flush=True)
        else:
            p = subprocess.Popen(["afplay", path])
            _PREVIEW_PROCS.append(p)
            print(f"[SETTINGS] preview fallback (afplay): {raw}", flush=True)
