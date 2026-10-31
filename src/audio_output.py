# src/audio_output.py
"""
Управление аудиовыходом macOS через CoreAudio (ctypes).
Без внешних утилит (SwitchAudioSource не нужен).

Основные функции:
  - list_output_devices() -> list[dict]   # [{"name": str, "id": int, "is_default": bool}, ...]
  - get_default_output_id() -> int | None
  - get_default_output_name() -> str | None
  - get_device_id_by_name(name: str) -> int | None
  - play_on_device(path, device_name, loops=0) -> tuple | None
      Проигрывает файл на конкретном устройстве через AVAudioEngine,
      НЕ меняя системный дефолт.
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

from AVFoundation import (
    AVAudioEngine,
    AVAudioFile,
    AVAudioPlayerNode,
)
from Foundation import NSURL

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

# AudioUnit: kAudioOutputUnitProperty_CurrentDevice = 2000, kAudioUnitScope_Global = 1
_kAudioOutputUnitProperty_CurrentDevice = 2000
_kAudioUnitScope_Global = 1

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

_coreaudio: CDLL | None
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


_HAS_CF: bool = False

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
    assert _coreaudio is not None
    size = c_uint32(0)
    status = _coreaudio.AudioObjectGetPropertyDataSize(
        object_id, byref(address), 0, None, byref(size)
    )
    if status != 0:
        return None
    return size.value


def _get_property_data(object_id, address, data_size, out_buffer):
    assert _coreaudio is not None
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
    assert _coreaudio is not None
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
    if size is None:
        return False
    if size < ctypes.sizeof(c_uint32):
        return False
    return size // ctypes.sizeof(c_uint32) > 0


# ---------- Публичные функции: устройства ----------

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
    assert _coreaudio is not None
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


def get_device_id_by_name(name):
    if not name:
        return None
    for dev in list_output_devices():
        if dev["name"] == name:
            return dev["id"]
    return None


# ---------- Публичные функции: воспроизведение ----------

def play_on_device(path, device_name, loops=0):
    """Проиграть файл на конкретном устройстве, не меняя системный дефолт.

    Возвращает (engine, player, audio_file) — держать ссылки, пока играет.
    Если device_name == "Default" или устройство не найдено — вернуть None.
    Если AVAudioEngine не смог привязаться к устройству — вернуть None,
    вызывающий код откатится на NSSound (системный дефолт).
    """
    if not path or not device_name or device_name == "Default":
        return None

    device_id = get_device_id_by_name(device_name)
    if device_id is None:
        return None

    try:
        url = NSURL.fileURLWithPath_(path)
        audio_file, _err = AVAudioFile.alloc().initForReading_error_(url, None)
        if audio_file is None:
            return None

        engine = AVAudioEngine.alloc().init()
        player = AVAudioPlayerNode.alloc().init()
        engine.attachNode_(player)
        engine.connect_to_format_(player, engine.mainMixerNode(), audio_file.processingFormat())

        out_node = engine.outputNode()
        au = out_node.audioUnit()
        if au is None:
            return None

        # Привязать output node к устройству (kAudioOutputUnitProperty_CurrentDevice).
        # Это НЕ меняет kAudioHardwarePropertyDefaultOutputDevice.
        err = au.setProperty_withValue_forScope_element_(
            _kAudioOutputUnitProperty_CurrentDevice,
            c_uint32(device_id),
            _kAudioUnitScope_Global,
            0,
        )
        if err != 0:
            print(f"[DEBUG] play_on_device: set device rc={err}", flush=True)
            return None

        ok, err = engine.startAndReturnError_(None)
        if not ok:
            print(f"[DEBUG] play_on_device: engine start failed: {err}", flush=True)
            return None

        player.scheduleFile_atTime_completionHandler_(audio_file, None, None)
        if loops:
            player.setLoops_(loops)
        player.play()
        return (engine, player, audio_file)
    except Exception as e:
        print(f"[DEBUG] play_on_device failed: {e}", flush=True)
        return None


def stop_playing(handle):
    """Остановить engine/player из play_on_device."""
    if not handle:
        return
    try:
        engine, player, _audio_file = handle
        try:
            player.stop()
        except Exception:
            pass
        try:
            engine.stop()
        except Exception:
            pass
    except Exception:
        pass
