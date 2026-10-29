# src/dialogs.py
import objc
import subprocess
import os
from datetime import datetime, timedelta
import EventKit
from Foundation import NSDate, NSObject, NSTimer
from AppKit import (
    NSPanel, NSTextField, NSButton, NSColor, NSFont, NSMakeRect,
    NSBezelStyleRounded, NSStatusWindowLevel, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSBackingStoreBuffered,
    NSApplication, NSApplicationActivationPolicyRegular,
    NSApplicationActivationPolicyAccessory,
    NSPasteboard, NSSound,
    NSLineBreakByTruncatingTail,
    NSVisualEffectView, NSVisualEffectMaterialHUDWindow,
    NSVisualEffectBlendingModeBehindWindow, NSVisualEffectStateActive,
    NSViewWidthSizable, NSViewHeightSizable
)
from ui_utils import format_event_datetime
from config import CONFIG
import audio_output

# Глобальные хранилища — чтобы GC не собрал панели, обработчики, звук, таймеры
_RETAINED_PANELS = {}
_RETAINED_HANDLERS = {}
_RETAINED_STATE = {}

POST_MEETING_MINUTES = 3
MAX_ALARM_LIFETIME_MINUTES = 30
MIN_ALARM_LIFETIME_SECONDS = 60


class DialogHandler(NSObject):
    def initWithAction_(self, action):
        self = objc.super(DialogHandler, self).init()
        if self is None:
            return None
        self.action = action
        return self

    def performAction_(self, sender):
        self.action()


# ---------- Аудиовыход (обёртка над audio_output) ----------

def _get_audio_outputs():
    """Список имён устройств вывода + 'Default' в начале."""
    try:
        devices = audio_output.list_output_devices()
    except Exception as e:
        print(f"[DEBUG] audio_output.list_output_devices failed: {e}", flush=True)
        devices = []
    return ["Default"] + [d["name"] for d in devices]


def _switch_audio_output(device_name):
    """Переключает системный вывод на device_name. Возвращает True при успехе."""
    if not device_name or device_name == "Default":
        return False
    try:
        return audio_output.set_default_output_by_name(device_name)
    except Exception as e:
        print(f"[DEBUG] audio_output.set_default_output_by_name failed: {e}", flush=True)
        return False


def _restore_audio_output(device_id):
    """Восстанавливает системный вывод по AudioDeviceID."""
    if device_id is None:
        return
    try:
        audio_output.set_default_output(device_id)
    except Exception as e:
        print(f"[DEBUG] audio_output.set_default_output failed: {e}", flush=True)


# ---------- Управление окнами будильника ----------

def _close_alarm(panel_id):
    state = _RETAINED_STATE.pop(panel_id, None)
    if state:
        snd = state.get("sound")
        if snd:
            try:
                snd.stop()
            except Exception:
                pass
        tmr = state.get("timer")
        if tmr:
            try:
                tmr.invalidate()
            except Exception:
                pass
        orig = state.get("original_output_id")
        if orig is not None:
            _restore_audio_output(orig)

    panel = _RETAINED_PANELS.pop(panel_id, None)
    if panel:
        try:
            panel.orderOut_(None)
            panel.close()
        except Exception:
            pass
    _RETAINED_HANDLERS.pop(panel_id, None)


def close_all_alarms():
    ids = list(_RETAINED_PANELS.keys())
    for pid in ids:
        _close_alarm(pid)


def _bring_to_front(panel):
    app = NSApplication.sharedApplication()
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
    try:
        panel.setCollectionBehavior_((1 << 0) | (1 << 4) | (1 << 6))
    except Exception:
        pass
    panel.makeKeyAndOrderFront_(None)
    panel.orderFrontRegardless()


def _restore_accessory(app):
    try:
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def _make_button(title, frame, handler, bold=False):
    btn = NSButton.alloc().initWithFrame_(frame)
    btn.setTitle_(title)
    btn.setBezelStyle_(NSBezelStyleRounded)
    btn.setFont_(NSFont.systemFontOfSize_(13) if not bold else NSFont.boldSystemFontOfSize_(13))
    btn.setTarget_(handler)
    btn.setAction_("performAction:")
    return btn


def _open_url(url):
    try:
        subprocess.Popen(["open", url])
    except Exception as e:
        print(f"[DEBUG] open failed: {e}", flush=True)


def _compute_alarm_lifetime(events_data, now):
    """Живёт до max(start + POST_MEETING, end), но не дольше MAX_ALARM_LIFETIME_MINUTES.
    Если всё в прошлом — MIN_ALARM_LIFETIME_SECONDS.
    """
    post = timedelta(minutes=POST_MEETING_MINUTES)
    latest = None
    for ev in events_data:
        s = ev.get("start")
        e = ev.get("end")
        if s is None:
            continue
        deadline = s + post
        if e is not None and e > deadline:
            deadline = e
        if latest is None or deadline > latest:
            latest = deadline
    if latest is None:
        return MIN_ALARM_LIFETIME_SECONDS
    seconds = (latest - now).total_seconds()
    if seconds < MIN_ALARM_LIFETIME_SECONDS:
        seconds = MIN_ALARM_LIFETIME_SECONDS
    if seconds > MAX_ALARM_LIFETIME_MINUTES * 60:
        seconds = MAX_ALARM_LIFETIME_MINUTES * 60
    return int(seconds)


def show_alarm(events_data):
    close_all_alarms()

    app = NSApplication.sharedApplication()
    now = datetime.now()

    padding = 20
    events_h = max(1, len(events_data)) * 56
    buttons_h = 40
    header_h = 12
    width = 560
    height = padding * 2 + header_h + events_h + 16 + buttons_h

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
        NSBackingStoreBuffered,
        False
    )
    panel.setTitle_("")
    panel.setLevel_(NSStatusWindowLevel)
    panel.center()
    panel.setReleasedWhenClosed_(False)
    panel.setHidesOnDeactivate_(False)
    panel.setFloatingPanel_(True)
    panel.setTitleVisibility_(1)
    panel.setTitlebarAppearsTransparent_(True)

    effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    effect.setMaterial_(NSVisualEffectMaterialHUDWindow)
    effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    effect.setState_(NSVisualEffectStateActive)
    effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    panel.setContentView_(effect)
    content = effect

    y = height - padding
    first_location = None

    for ev in events_data:
        title_text = (ev.get("title") or "Untitled").strip()

        title_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(padding, y - 22, width - padding * 2, 22)
        )
        title_field.setStringValue_(title_text)
        title_field.setBezeled_(False)
        title_field.setDrawsBackground_(False)
        title_field.setEditable_(False)
        title_field.setSelectable_(False)
        title_field.setFont_(NSFont.boldSystemFontOfSize_(15))
        title_field.setTextColor_(NSColor.labelColor())
        title_field.setLineBreakMode_(NSLineBreakByTruncatingTail)
        content.addSubview_(title_field)
        y -= 24

        time_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(padding, y - 18, width - padding * 2, 18)
        )
        time_field.setStringValue_(format_event_datetime(ev["start"], now))
        time_field.setBezeled_(False)
        time_field.setDrawsBackground_(False)
        time_field.setEditable_(False)
        time_field.setSelectable_(False)
        time_field.setFont_(NSFont.systemFontOfSize_(12))
        time_field.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(time_field)
        y -= 28

        if ev.get("location") and not first_location:
            first_location = ev["location"]

    btn_y = padding
    btn_h = 32
    gap = 10
    btn_w = 150
    close_w = 110

    handlers = {}
    panel_id = id(panel)

    def close_action():
        _close_alarm(panel_id)
        _restore_accessory(NSApplication.sharedApplication())

    right_x = width - padding

    # Закрыть
    right_x -= close_w
    h_close = DialogHandler.alloc().initWithAction_(close_action)
    btn_close = _make_button("Закрыть", NSMakeRect(right_x, btn_y, close_w, btn_h), h_close, bold=True)
    content.addSubview_(btn_close)
    handlers["close"] = h_close
    right_x -= gap

    # Копировать
    right_x -= btn_w
    def copy_action():
        parts = []
        for ev in events_data:
            title = (ev.get('title') or 'Untitled').strip()
            parts.append(f"📅 Event: {title}")
            parts.append(format_event_datetime(ev['start'], now))
            if ev.get('url'):
                parts.append(f"🔗 {ev['url']}")
            if ev.get('location'):
                parts.append(f"📍 {ev['location']}")
            parts.append("")
        text = "\n".join(parts).rstrip() + "\n"
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, "public.utf8-plain-text")
        close_action()

    h_copy = DialogHandler.alloc().initWithAction_(copy_action)
    btn_copy = _make_button("Копировать", NSMakeRect(right_x, btn_y, btn_w, btn_h), h_copy)
    content.addSubview_(btn_copy)
    handlers["copy"] = h_copy
    right_x -= gap

    # Открыть встречу (Location)
    if first_location:
        right_x -= btn_w
        if right_x < padding:
            right_x = padding
        def open_meeting_action(loc=first_location):
            _open_url(loc)
            close_action()
        h_loc = DialogHandler.alloc().initWithAction_(open_meeting_action)
        btn = _make_button("Открыть встречу", NSMakeRect(right_x, btn_y, btn_w, btn_h), h_loc, bold=True)
        content.addSubview_(btn)
        handlers["open_location"] = h_loc

    # --- Звук с запоминанием и переключением аудиовыхода ---
    original_output_id = None
    try:
        original_output_id = audio_output.get_default_output_id()
    except Exception as e:
        print(f"[DEBUG] get_default_output_id failed: {e}", flush=True)

    output_device = CONFIG.get("sound_output_device", "Default")
    if output_device and output_device != "Default":
        _switch_audio_output(output_device)

    sound_path = CONFIG.get("sound_file", "/System/Library/Sounds/Hero.aiff")
    sound = None
    if os.path.exists(sound_path):
        sound = NSSound.alloc().initWithContentsOfFile_byReference_(sound_path, True)
        if sound:
            try:
                sound.setLoops_(-1)
                sound.setVolume_(0.9)
                sound.play()
            except Exception as e:
                print(f"[DEBUG] sound play failed: {e}", flush=True)

    lifetime = _compute_alarm_lifetime(events_data, now)
    print(f"[DEBUG] Alarm lifetime: {lifetime} sec ({lifetime/60:.1f} min)", flush=True)

    def auto_close():
        _close_alarm(panel_id)
        _restore_accessory(NSApplication.sharedApplication())

    h_auto = DialogHandler.alloc().initWithAction_(auto_close)
    handlers["auto"] = h_auto
    timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        lifetime, h_auto, "performAction:", None, False
    )

    _RETAINED_PANELS[panel_id] = panel
    _RETAINED_HANDLERS[panel_id] = handlers
    _RETAINED_STATE[panel_id] = {
        "sound": sound,
        "timer": timer,
        "original_output_id": original_output_id,
    }

    _bring_to_front(panel)
    return True
