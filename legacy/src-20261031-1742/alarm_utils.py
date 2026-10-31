# src/alarm_utils.py
import os
import subprocess
from datetime import timedelta
from typing import Any

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApplicationActivationPolicyRegular,
    NSBezelStyleRounded,
    NSButton,
    NSFont,
    NSSound,
)
from Foundation import NSObject, NSTimer

import audio_output
from config import CONFIG

# Ключ — id(panel), значение — NSObject/dict/NSTimer
_RETAINED_PANELS: dict[int, Any] = {}
_RETAINED_HANDLERS: dict[int, Any] = {}
_RETAINED_STATE: dict[int, Any] = {}

POST_MEETING_MINUTES = 3
MIN_ALARM_LIFETIME_SECONDS = 60
SNOOZE_MINUTES = 5

_MAX_LOG_BYTES = 5 * 1024 * 1024
_DEBUG_LOG = "/tmp/notifyme_debug.log"


def _rotate_logs():
    try:
        if os.path.exists(_DEBUG_LOG) and os.path.getsize(_DEBUG_LOG) > _MAX_LOG_BYTES:
            with open(_DEBUG_LOG, "rb") as f:
                f.seek(-_MAX_LOG_BYTES, os.SEEK_END)
                tail = f.read()
            with open(_DEBUG_LOG, "wb") as f:
                f.write(b"[ROTATED]\n")
                f.write(tail)
    except Exception as e:
        print(f"[DEBUG] rotate logs failed: {e}", flush=True)


_rotate_logs()


def _sound_on_seconds():
    try:
        return max(1, int(CONFIG.get("alarm_sound_on_seconds", 12)))
    except Exception:
        return 12


def _sound_off_seconds():
    try:
        return max(1, int(CONFIG.get("alarm_sound_off_seconds", 60)))
    except Exception:
        return 60


def _resolve_sound_path_for(name):
    if not name:
        return None
    candidates = []
    if os.path.isabs(name):
        candidates.append(name)
    else:
        candidates.append(f"/System/Library/Sounds/{name}")
        if not name.endswith((".aiff", ".mp3", ".wav")):
            candidates.append(f"/System/Library/Sounds/{name}.aiff")
        candidates.append(os.path.join(os.path.dirname(__file__), "sounds", name))
        candidates.append(os.path.join(os.path.dirname(__file__), "..", "assets", "sounds", name))
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def _resolve_sound_path():
    return _resolve_sound_path_for(CONFIG.get("sound_file", "droid-meeting.mp3"))


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
    """Проигрывает звук alarm на выбранном устройстве, не трогая системный дефолт.

    Если play_on_device недоступен (устройство не найдено, AVAudioEngine не привязался),
    фолбэк — NSSound на системном дефолте (без переключения).
    """

    def initWithPath_device_state_(self, path, device_name, state):
        self = objc.super(PulseController, self).init()
        if self is None:
            return None
        self._path = path
        self._device = device_name or "Default"
        self._state = state
        self._stopped = False
        self._handles: list[Any] = []
        self._fallback_sound = None
        return self

    def _play(self):
        if self._stopped:
            return
        handle = audio_output.play_on_device(self._path, self._device, loops=0)
        if handle is not None:
            self._handles.append(handle)
            self._schedule_off()
            return

        # Фолбэк: NSSound на системном дефолте (без переключения устройства)
        print(f"[DEBUG] pulse fallback to NSSound ({self._device!r})", flush=True)
        snd = NSSound.alloc().initWithContentsOfFile_byReference_(self._path, True)
        if snd:
            snd.setLoops_(0)
            try:
                snd.setVolume_(0.9)
            except Exception:
                pass
            snd.play()
            self._fallback_sound = snd
        self._schedule_off()

    def _schedule_off(self):
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _sound_on_seconds(), self, "offPulse:", None, False
        )

    def _stop_handles(self):
        for h in self._handles:
            audio_output.stop_playing(h)
        self._handles = []
        snd = self._fallback_sound
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass
            self._fallback_sound = None

    def start_(self, timer=None):
        if self._stopped:
            return
        self._play()

    def offPulse_(self, timer):
        if self._stopped:
            return
        self._stop_handles()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _sound_off_seconds(), self, "start:", None, False
        )

    def stop_(self, timer=None):
        self._stopped = True
        self._stop_handles()


def _get_audio_outputs():
    try:
        devices = audio_output.list_output_devices()
    except Exception as e:
        print(f"[DEBUG] audio_output.list_output_devices failed: {e}", flush=True)
        devices = []
    return ["Default"] + [d["name"] for d in devices]


def _stop_sound(state):
    pc = state.get("pulse_controller")
    if pc is not None:
        try:
            pc.stop_(None)
        except Exception:
            pass
        state["pulse_controller"] = None
    tmr = state.get("pulse_timer")
    if tmr:
        try:
            tmr.invalidate()
        except Exception:
            pass
        state["pulse_timer"] = None


def _close_alarm(panel_id):
    state = _RETAINED_STATE.pop(panel_id, None)
    if state:
        _stop_sound(state)
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
