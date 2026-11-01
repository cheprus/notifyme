# src/audio_output.py
"""
Playback на конкретном устройстве через временное переключение
системного default output.

Почему так:
- HAL AudioUnit и AVAudioEngine + CurrentDevice не работают надёжно
  на всех macOS/устройствах.
- Переключение kAudioHardwarePropertyDefaultOutputDevice + NSSound
  работает всегда, на любом устройстве.
- Дефолт возвращается после окончания или по stop().
"""

import ctypes
import threading
from ctypes import (
    CDLL,
    POINTER,
    Structure,
    byref,
    c_char_p,
    c_int,
    c_uint32,
    c_void_p,
)

from AppKit import NSSound

# ---------- CoreAudio константы ----------

kAudioObjectSystemObject = 1
kAudioObjectPropertyScopeGlobal = 1
kAudioObjectPropertyElementMaster = 0
kAudioObjectPropertyElementMain = 0

kAudioHardwarePropertyDevices = 0x64657623
kAudioHardwarePropertyDefaultOutputDevice = 0x644f7574

kAudioDevicePropertyDeviceNameCFString = 0x6c6e616d
kAudioDevicePropertyStreams = 0x73746d23
kAudioDevicePropertyScopeOutput = 0x6f757470

AudioObjectID = c_uint32
AudioDeviceID = c_uint32
OSStatus = c_int


class AudioObjectPropertyAddress(Structure):
    _fields_ = [
        ("mSelector", c_uint32),
        ("mScope", c_uint32),
        ("mElement", c_uint32),
    ]


def _load(framework, path_variants):
    for p in path_variants:
        try:
            return CDLL(p)
        except OSError:
            continue
    return None


_coreaudio = _load("CoreAudio", [
    "/System/Library/Frameworks/CoreAudio.framework/Versions/A/CoreAudio",
    "/System/Library/Frameworks/CoreAudio.framework/CoreAudio",
])
_cf = _load("CoreFoundation", [
    "/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation",
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
])

_HAS_CF = _cf is not None
_HAS_CORE = _coreaudio is not None

if _HAS_CORE:
    _coreaudio.AudioObjectGetPropertyDataSize.argtypes = [
        AudioObjectID, POINTER(AudioObjectPropertyAddress), c_uint32, c_void_p, POINTER(c_uint32),
    ]
    _coreaudio.AudioObjectGetPropertyDataSize.restype = OSStatus

    _coreaudio.AudioObjectGetPropertyData.argtypes = [
        AudioObjectID, POINTER(AudioObjectPropertyAddress), c_uint32, c_void_p,
        POINTER(c_uint32), c_void_p,
    ]
    _coreaudio.AudioObjectGetPropertyData.restype = OSStatus

    _coreaudio.AudioObjectSetPropertyData.argtypes = [
        AudioObjectID, POINTER(AudioObjectPropertyAddress), c_uint32, c_void_p,
        c_uint32, c_void_p,
    ]
    _coreaudio.AudioObjectSetPropertyData.restype = OSStatus

if _HAS_CF:
    _cf.CFStringGetCStringPtr.argtypes = [c_void_p, c_uint32]
    _cf.CFStringGetCStringPtr.restype = c_char_p
    _cf.CFStringGetLength.argtypes = [c_void_p]
    _cf.CFStringGetLength.restype = c_int
    _cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_int, c_uint32]
    _cf.CFStringGetCString.restype = ctypes.c_bool
    _cf.CFRelease.argtypes = [c_void_p]
    _cf.CFRelease.restype = None


_kCFStringEncodingUTF8 = 0x08000100


def _make_address(selector, scope=kAudioObjectPropertyScopeGlobal, element=kAudioObjectPropertyElementMaster):
    return AudioObjectPropertyAddress(selector, scope, element)


def _get_property_data_size(object_id, address):
    size = c_uint32(0)
    status = _coreaudio.AudioObjectGetPropertyDataSize(
        object_id, byref(address), 0, None, byref(size)
    )
    if status != 0:
        return None
    return size.value


def _get_property_data(object_id, address, data_size, out_buffer):
    size = c_uint32(data_size)
    status = _coreaudio.AudioObjectGetPropertyData(
        object_id, byref(address), 0, None, byref(size), out_buffer
    )
    if status != 0:
        return None
    return size.value


def _get_device_name(device_id):
    if not _HAS_CF:
        return None
    address = _make_address(kAudioDevicePropertyDeviceNameCFString)
    size = _get_property_data_size(device_id, address)
    if size is None or size == 0:
        return None
    cfstr_ref = c_void_p()
    size = c_uint32(ctypes.sizeof(cfstr_ref))
    status = _coreaudio.AudioObjectGetPropertyData(
        device_id, byref(address), 0, None, byref(size), byref(cfstr_ref)
    )
    if status != 0 or not cfstr_ref.value:
        return None
    try:
        ptr = _cf.CFStringGetCStringPtr(cfstr_ref.value, _kCFStringEncodingUTF8)
        if ptr:
            return ptr.decode("utf-8", errors="replace")
        length = _cf.CFStringGetLength(cfstr_ref.value)
        buf_size = (length + 1) * 4
        buf = ctypes.create_string_buffer(buf_size)
        ok = _cf.CFStringGetCString(cfstr_ref.value, buf, buf_size, _kCFStringEncodingUTF8)
        if ok:
            return buf.value.decode("utf-8", errors="replace")
        return None
    finally:
        try:
            _cf.CFRelease(cfstr_ref.value)
        except Exception:
            pass


def _device_has_output(device_id):
    address = _make_address(
        kAudioDevicePropertyStreams,
        scope=kAudioDevicePropertyScopeOutput,
        element=kAudioObjectPropertyElementMain,
    )
    size = _get_property_data_size(device_id, address)
    if size is None or size < ctypes.sizeof(c_uint32):
        return False
    return size // ctypes.sizeof(c_uint32) > 0


# ---------- Публичные функции: устройства ----------

def is_available():
    return _HAS_CORE and _HAS_CF


def list_output_devices():
    if not is_available():
        return []

    address = _make_address(kAudioHardwarePropertyDevices)
    size = _get_property_data_size(kAudioObjectSystemObject, address)
    if size is None or size == 0:
        return []
    count = size // ctypes.sizeof(c_uint32)
    if count == 0:
        return []

    ids = (c_uint32 * count)()
    got = _get_property_data(kAudioObjectSystemObject, address, size, ids)
    if got is None:
        return []

    default_id = get_default_output_id()
    devices = []
    for dev_id in ids:
        if not _device_has_output(dev_id):
            continue
        name = _get_device_name(dev_id)
        if not name:
            continue
        devices.append({
            "name": name,
            "id": int(dev_id),
            "is_default": (default_id is not None and int(dev_id) == default_id),
        })
    return devices


def get_default_output_id():
    if not is_available():
        return None
    address = _make_address(kAudioHardwarePropertyDefaultOutputDevice)
    dev_id = c_uint32(0)
    size = c_uint32(ctypes.sizeof(dev_id))
    status = _coreaudio.AudioObjectGetPropertyData(
        kAudioObjectSystemObject, byref(address), 0, None, byref(size), byref(dev_id)
    )
    if status != 0:
        return None
    return int(dev_id.value)


def set_default_output_id(device_id):
    if not is_available():
        return False
    address = _make_address(kAudioHardwarePropertyDefaultOutputDevice)
    dev_id = c_uint32(device_id)
    status = _coreaudio.AudioObjectSetPropertyData(
        kAudioObjectSystemObject, byref(address), 0, None,
        ctypes.sizeof(dev_id), byref(dev_id),
    )
    return status == 0


def get_default_output_name():
    dev_id = get_default_output_id()
    if dev_id is None:
        return None
    return _get_device_name(dev_id)


def get_device_id_by_name(name):
    if not name:
        return None
    for dev in list_output_devices():
        if dev["name"] == name:
            return dev["id"]
    return None


# ---------- Playback через переключение дефолта + NSSound ----------

class _PlaybackHandle:
    __slots__ = ("sound", "original_id", "stopped", "lock")

    def __init__(self, sound, original_id):
        self.sound = sound
        self.original_id = original_id
        self.stopped = False
        self.lock = threading.Lock()

    def stop(self):
        with self.lock:
            if self.stopped:
                return
            self.stopped = True
            try:
                if self.sound is not None:
                    self.sound.stop()
            except Exception:
                pass
            if self.original_id is not None:
                ok = set_default_output_id(self.original_id)
                print(f"[AUDIO] restored default device id={self.original_id} ok={ok}", flush=True)
            self.sound = None
            self.original_id = None


def play_on_device(path, device_name, loops=0):
    """Проиграть файл на устройстве через переключение системного дефолта."""
    if not path or not device_name or device_name == "Default":
        return None
    if not is_available():
        return None

    device_id = get_device_id_by_name(device_name)
    if device_id is None:
        print(f"[AUDIO] play_on_device: device not found: {device_name!r}", flush=True)
        return None

    original_id = get_default_output_id()
    if original_id == device_id:
        print(f"[AUDIO] {device_name!r} is already default, playing directly", flush=True)
    else:
        ok = set_default_output_id(device_id)
        if not ok:
            print(f"[AUDIO] set_default_output_id({device_id}) failed", flush=True)
            return None
        print(f"[AUDIO] switched default: {original_id} -> {device_id} ({device_name!r})", flush=True)

    try:
        sound = NSSound.alloc().initWithContentsOfFile_byReference_(path, True)
        if sound is None:
            print(f"[AUDIO] NSSound failed to load {path!r}", flush=True)
            if original_id is not None:
                set_default_output_id(original_id)
            return None
        try:
            sound.setLoops_(loops)
        except Exception:
            pass
        if not sound.play():
            print("[AUDIO] NSSound.play() returned False", flush=True)
            if original_id is not None:
                set_default_output_id(original_id)
            return None
        print(f"[AUDIO] playing {path} on {device_name!r} (device_id={device_id})", flush=True)
        return _PlaybackHandle(sound, original_id)
    except Exception as e:
        print(f"[AUDIO] play_on_device failed: {e}", flush=True)
        if original_id is not None:
            set_default_output_id(original_id)
        return None


def stop_playing(handle):
    if not handle:
        return
    try:
        handle.stop()
    except Exception as e:
        print(f"[AUDIO] stop_playing failed: {e}", flush=True)
