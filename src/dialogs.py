# src/dialogs.py
import objc
import subprocess
import os
from datetime import datetime, timedelta
import EventKit
from Foundation import NSDate, NSObject, NSTimer
from AppKit import (
    NSPanel, NSTextField, NSButton, NSColor, NSFont, NSMakeRect,
    NSBezelStyleRounded, NSScreenSaverWindowLevel, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSBackingStoreBuffered,
    NSApplication, NSApplicationActivationPolicyRegular,
    NSApplicationActivationPolicyAccessory,
    NSPasteboard, NSSound,
    NSLineBreakByTruncatingTail,
    NSVisualEffectView, NSVisualEffectMaterialHUDWindow,
    NSVisualEffectBlendingModeBehindWindow, NSVisualEffectStateActive,
    NSViewWidthSizable, NSViewHeightSizable
)
from ui_utils import (
    format_event_datetime,
    format_event_datetime_for_copy,
)
from config import CONFIG
import audio_output

_RETAINED_PANELS = {}
_RETAINED_HANDLERS = {}
_RETAINED_STATE = {}

POST_MEETING_MINUTES = 3
MIN_ALARM_LIFETIME_SECONDS = 60

SNOOZE_MINUTES = 5


def _sound_on_seconds():
    try:
        return max(1, int(CONFIG.get("alarm_sound_on_seconds", 10)))
    except Exception:
        return 10


def _sound_off_seconds():
    try:
        return max(1, int(CONFIG.get("alarm_sound_off_seconds", 60)))
    except Exception:
        return 60


class DialogHandler(NSObject):
    def initWithAction_(self, action):
        self = objc.super(DialogHandler, self).init()
        if self is None:
            return None
        self.action = action
        return self

    def performAction_(self, sender):
        self.action()


class PulseController(NSObject):
    """Пульс звука: N сек вкл, M сек выкл, до закрытия."""
    def initWithSound_state_(self, sound, state):
        self = objc.super(PulseController, self).init()
        if self is None:
            return None
        self._sound = sound
        self._state = state
        self._stopped = False
        return self

    def start_(self, timer=None):
        if self._stopped or self._sound is None:
            return
        try:
            self._sound.play()
        except Exception as e:
            print(f"[DEBUG] pulse play failed: {e}", flush=True)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _sound_on_seconds(), self, "offPulse:", None, False
        )

    def offPulse_(self, timer):
        if self._stopped or self._sound is None:
            return
        try:
            self._sound.stop()
        except Exception:
            pass
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _sound_off_seconds(), self, "start:", None, False
        )

    def stop_(self, timer=None):
        self._stopped = True
        if self._sound is not None:
            try:
                self._sound.stop()
            except Exception:
                pass


def _get_audio_outputs():
    try:
        devices = audio_output.list_output_devices()
    except Exception as e:
        print(f"[DEBUG] audio_output.list_output_devices failed: {e}", flush=True)
        devices = []
    return ["Default"] + [d["name"] for d in devices]


def _switch_audio_output(device_name):
    if not device_name or device_name == "Default":
        return False
    try:
        return audio_output.set_default_output_by_name(device_name)
    except Exception as e:
        print(f"[DEBUG] audio_output.set_default_output_by_name failed: {e}", flush=True)
        return False


def _restore_audio_output(device_id):
    if device_id is None:
        return
    try:
        audio_output.set_default_output(device_id)
    except Exception as e:
        print(f"[DEBUG] audio_output.set_default_output failed: {e}", flush=True)


def _stop_sound(state):
    snd = state.get("sound")
    if snd:
        try:
            snd.stop()
        except Exception:
            pass
    tmr = state.get("pulse_timer")
    if tmr:
        try:
            tmr.invalidate()
        except Exception:
            pass
        state["pulse_timer"] = None
    pc = state.get("pulse_controller")
    if pc is not None:
        try:
            pc.stop_(None)
        except Exception:
            pass
        state["pulse_controller"] = None


def _close_alarm(panel_id):
    state = _RETAINED_STATE.pop(panel_id, None)
    if state:
        _stop_sound(state)
        orig = state.get("original_output_id")
        if orig is not None:
            _restore_audio_output(orig)
        life = state.get("life_timer")
        if life:
            try:
                life.invalidate()
            except Exception:
                pass

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
    max_minutes = CONFIG.get("auto_close_minutes", 15)
    max_seconds = max_minutes * 60
    if seconds > max_seconds:
        seconds = max_seconds
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
    panel.setLevel_(NSScreenSaverWindowLevel)
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

    state = {
        "sound": None,
        "pulse_timer": None,
        "life_timer": None,
        "original_output_id": None,
        "pulse_controller": None,
    }

    def close_action():
        _close_alarm(panel_id)
        _restore_accessory(NSApplication.sharedApplication())

    def mute_action():
        """Заглушить звук, окно оставить."""
        _stop_sound(state)
        try:
            btn_mute.setTitle_("🔇 Заглушено")
            btn_mute.setEnabled_(False)
        except Exception:
            pass
        print("[DEBUG] Alarm muted (window stays)", flush=True)

    def snooze_action():
        _close_alarm(panel_id)
        _restore_accessory(NSApplication.sharedApplication())
        snooze_secs = SNOOZE_MINUTES * 60
        def re_alarm():
            try:
                show_alarm(events_data)
            except Exception as e:
                print(f"[DEBUG] snooze show_alarm failed: {e}", flush=True)
        h_re = DialogHandler.alloc().initWithAction_(re_alarm)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            snooze_secs, h_re, "performAction:", None, False
        )
        _RETAINED_HANDLERS.setdefault("snooze_timers", []).append(h_re)
        print(f"[DEBUG] Snooze: next alarm in {SNOOZE_MINUTES} min", flush=True)

    right_x = width - padding

    # Закрыть
    right_x -= close_w
    h_close = DialogHandler.alloc().initWithAction_(close_action)
    btn_close = _make_button("Закрыть", NSMakeRect(right_x, btn_y, close_w, btn_h), h_close, bold=True)
    content.addSubview_(btn_close)
    handlers["close"] = h_close
    right_x -= gap

    # Отложить
    snooze_w = 140
    right_x -= snooze_w
    h_snooze = DialogHandler.alloc().initWithAction_(snooze_action)
    btn_snooze = _make_button(f"Отложить {SNOOZE_MINUTES} мин", NSMakeRect(right_x, btn_y, snooze_w, btn_h), h_snooze)
    content.addSubview_(btn_snooze)
    handlers["snooze"] = h_snooze
    right_x -= gap

    # Заглушить
    mute_w = 130
    right_x -= mute_w
    h_mute = DialogHandler.alloc().initWithAction_(mute_action)
    btn_mute = _make_button("🔇 Заглушить", NSMakeRect(right_x, btn_y, mute_w, btn_h), h_mute)
    content.addSubview_(btn_mute)
    handlers["mute"] = h_mute
    right_x -= gap

    # Копировать (COPY timezone)
    right_x -= btn_w
    def copy_action():
        parts = []
        for ev in events_data:
            title = (ev.get('title') or 'Untitled').strip()
            parts.append(f"📅 Event: {title}")
            parts.append(format_event_datetime_for_copy(ev['start'], now))
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

    # Открыть встречу
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

    # Звук + пульс
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
                sound.setLoops_(0)
                sound.setVolume_(0.9)
            except Exception as e:
                print(f"[DEBUG] sound setup failed: {e}", flush=True)

    state["sound"] = sound
    state["original_output_id"] = original_output_id

    if sound:
        pulse = PulseController.alloc().initWithSound_state_(sound, state)
        state["pulse_controller"] = pulse
        pulse.start_(None)

    lifetime = _compute_alarm_lifetime(events_data, now)
    print(f"[DEBUG] Alarm lifetime: {lifetime} sec ({lifetime/60:.1f} min)", flush=True)

    def auto_close():
        _close_alarm(panel_id)
        _restore_accessory(NSApplication.sharedApplication())

    h_auto = DialogHandler.alloc().initWithAction_(auto_close)
    handlers["auto"] = h_auto
    life_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        lifetime, h_auto, "performAction:", None, False
    )
    state["life_timer"] = life_timer

    _RETAINED_PANELS[panel_id] = panel
    _RETAINED_HANDLERS[panel_id] = handlers
    _RETAINED_STATE[panel_id] = state

    _bring_to_front(panel)
    return True
