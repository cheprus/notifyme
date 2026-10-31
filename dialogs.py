# src/dialogs.py
import objc
import os
from datetime import datetime
from Foundation import NSObject, NSTimer
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

from alarm_utils import (
    _RETAINED_PANELS,
    _RETAINED_HANDLERS,
    _RETAINED_STATE,
    _resolve_sound_path,
    _get_audio_outputs,
    _switch_audio_output,
    _restore_audio_output,
    _stop_sound,
    _close_alarm,
    close_all_alarms,
    _bring_to_front,
    _restore_accessory,
    _make_button,
    _open_url,
    _compute_alarm_lifetime,
    DialogHandler,
    PulseController,
)


def _snooze_minutes():
    try:
        return max(1, int(CONFIG.get("snooze_minutes", 5)))
    except Exception:
        return 5


def show_alarm(events_data):
    close_all_alarms()

    app = NSApplication.sharedApplication()
    now = datetime.now()
    snooze_min = _snooze_minutes()

    padding = 20
    events_h = max(1, len(events_data)) * 56
    header_h = 12
    buttons_h = 40 + 40 + 8
    width = 620
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
        snooze_secs = snooze_min * 60
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
        print(f"[DEBUG] Snooze: next alarm in {snooze_min} min", flush=True)

    row1_y = padding
    row2_y = padding + 40 + 8
    btn_h = 32
    gap = 10

    row1_right = width - padding

    if first_location:
        w = 170
        row1_right -= w
        def open_meeting_action(loc=first_location):
            _open_url(loc)
            close_action()
        h_loc = DialogHandler.alloc().initWithAction_(open_meeting_action)
        btn = _make_button("🔗 Открыть встречу", NSMakeRect(row1_right, row1_y, w, btn_h), h_loc, bold=True)
        content.addSubview_(btn)
        handlers["open_location"] = h_loc
        row1_right -= gap

    w = 150
    row1_right -= w
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
    btn_copy = _make_button("📋 Копировать", NSMakeRect(row1_right, row1_y, w, btn_h), h_copy)
    content.addSubview_(btn_copy)
    handlers["copy"] = h_copy

    row2_right = width - padding

    close_w = 120
    row2_right -= close_w
    h_close = DialogHandler.alloc().initWithAction_(close_action)
    btn_close = _make_button("❌ Закрыть", NSMakeRect(row2_right, row2_y, close_w, btn_h), h_close, bold=True)
    content.addSubview_(btn_close)
    handlers["close"] = h_close
    row2_right -= gap

    snooze_w = 170
    row2_right -= snooze_w
    h_snooze = DialogHandler.alloc().initWithAction_(snooze_action)
    btn_snooze = _make_button(f"⏰ Отложить {snooze_min} мин", NSMakeRect(row2_right, row2_y, snooze_w, btn_h), h_snooze)
    content.addSubview_(btn_snooze)
    handlers["snooze"] = h_snooze
    row2_right -= gap

    mute_w = 150
    row2_right -= mute_w
    h_mute = DialogHandler.alloc().initWithAction_(mute_action)
    btn_mute = _make_button("🔇 Заглушить", NSMakeRect(row2_right, row2_y, mute_w, btn_h), h_mute)
    content.addSubview_(btn_mute)
    handlers["mute"] = h_mute

    original_output_id = None
    try:
        original_output_id = audio_output.get_default_output_id()
    except Exception as e:
        print(f"[DEBUG] get_default_output_id failed: {e}", flush=True)

    output_device = CONFIG.get("sound_output_device", "Default")
    if output_device and output_device != "Default":
        _switch_audio_output(output_device)

    sound_path = _resolve_sound_path()
    print(f"[DEBUG] sound path: {sound_path}", flush=True)
    sound = None
    if sound_path and os.path.exists(sound_path):
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
