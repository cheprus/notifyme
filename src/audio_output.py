# src/audio_output.py
"""
Управление аудиовыходом macOS через CoreAudio (ctypes).
Без внешних утилит (SwitchAudioSource не нужен).

Основные функции:
  - list_output_devices() -> list[dict]   # [{"name": str, "id": int, "is_default": bool}, ...]
  - get_default_output_id() -> int | None
  - set_default_output(device_id: int) -> bool
  - set_default_output_by_name(name: str) -> bool
  - get_default_output_name() -> str | None
"""

import ctypes
import threading
from ctypes import (
    c_uint32, c_int, c_void_p, c_char_p,
    byref, Structure, POINTER,
)

# ---------- Константы CoreAudio ----------

kAudioObjectSystemObject = 1
kAudioObjectPropertyScopeGlobal = 1  # 'glob'
kAudioObjectPropertyElementMaster = 0
kAudioObjectPropertyElementMain = 0

kAudioHardwarePropertyDevices = 0x64657623  # 'dev#'
kAudioHardwarePropertyDefaultOutputDevice = 0x644f7574  # 'dOut'

kAudioDevicePropertyDeviceNameCFString = 0x6c6e616d  # 'lnam'
kAudioDevicePropertyStreams = 0x73746d23  # 'stm#'
kAudioDevicePropertyScopeOutput = 0x6f757470  # 'outp'

AudioObjectID = c_uint32
AudioDeviceID = c_uint32
OSStatus = c_int


class AudioObjectPropertyAddress(Structure):
    _fields_ = [
        ("mSelector", c_uint32),
        ("mScope", c_uint32),
        ("mElement", c_uint32),
    ]


# ---------- Загрузка CoreAudio ----------

try:
    _coreaudio = ctypes.CDLL(
        "/System/Library/Frameworks/CoreAudio.framework/Versions/A/CoreAudio"
    )
except OSError:
    try:
        _coreaudio = ctypes.CDLL(
            "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
        )
    except OSError:
        _coreaudio = None


if _coreaudio is not None:
    _coreaudio.AudioObjectGetPropertyDataSize.argtypes = [
        AudioObjectID,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        POINTER(c_uint32),
    ]
    _coreaudio.AudioObjectGetPropertyDataSize.restype = OSStatus

    _coreaudio.AudioObjectGetPropertyData.argtypes = [
        AudioObjectID,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        POINTER(c_uint32),
        c_void_p,
    ]
    _coreaudio.AudioObjectGetPropertyData.restype = OSStatus

    _coreaudio.AudioObjectSetPropertyData.argtypes = [
        AudioObjectID,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        c_uint32,
        c_void_p,
    ]
    _coreaudio.AudioObjectSetPropertyData.restype = OSStatus

    try:
        _cf = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation"
        )
        _cf.CFStringGetCStringPtr.argtypes = [c_void_p, c_uint32]
        _cf.CFStringGetCStringPtr.restype = c_char_p
        _cf.CFStringGetLength.argtypes = [c_void_p]
        _cf.CFStringGetLength.restype = c_int
        _cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_int, c_uint32]
        _cf.CFStringGetCString.restype = ctypes.c_bool
        _cf.CFRelease.argtypes = [c_void_p]
        _cf.CFRelease.restype = None
        _HAS_CF = True
    except OSError:
        _HAS_CF = False


_kCFStringEncodingUTF8 = 0x08000100
_LOCK = threading.RLock()


# ---------- Внутренние помощники ----------

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
    """True, если у устройства есть хотя бы один output-стрим.
    Использует kAudioDevicePropertyStreams в scope Output — надёжнее,
    чем AudioBufferList, который на macOS Tahoe читается с padding.
    """
    address = _make_address(
        kAudioDevicePropertyStreams,
        scope=kAudioDevicePropertyScopeOutput,
        element=kAudioObjectPropertyElementMain,
    )
    size = _get_property_data_size(device_id, address)
    if size is None:
        return False
    if size < ctypes.sizeof(c_uint32):
        return False
    return size // ctypes.sizeof(c_uint32) > 0


# ---------- Публичные функции ----------

def is_available():
    return _coreaudio is not None and _HAS_CF


def list_output_devices():
    if not is_available():
        return []

    devices = []
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


def get_default_output_name():
    dev_id = get_default_output_id()
    if dev_id is None:
        return None
    return _get_device_name(dev_id)


def set_default_output(device_id):
    if not is_available():
        return False
    if not isinstance(device_id, int) or device_id <= 0:
        return False
    with _LOCK:
        address = _make_address(kAudioHardwarePropertyDefaultOutputDevice)
        dev_id = c_uint32(device_id)
        size = c_uint32(ctypes.sizeof(dev_id))
        status = _coreaudio.AudioObjectSetPropertyData(
            kAudioObjectSystemObject, byref(address), 0, None, size, byref(dev_id)
        )
        return status == 0


def set_default_output_by_name(name):
    if not name:
        return False
    for dev in list_output_devices():
        if dev["name"] == name:
            return set_default_output(dev["id"])
    return False


def get_device_id_by_name(name):
    if not name:
        return None
    for dev in list_output_devices():
        if dev["name"] == name:
            return dev["id"]
    return None


def restore_default_output():
    return True
