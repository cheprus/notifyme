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
    c_uint32, c_int, c_void_p, c_char_p, c_double,
    byref, Structure, POINTER, CFUNCTYPE
)

# ---------- Константы CoreAudio ----------

kAudioObjectSystemObject = 1
kAudioObjectPropertyScopeGlobal = 1  # 'glob'
kAudioObjectPropertyElementMaster = 0

kAudioHardwarePropertyDevices = 0x64657623  # 'dev#'
kAudioHardwarePropertyDefaultOutputDevice = 0x644f7574  # 'dOut'

kAudioDevicePropertyDeviceNameCFString = 0x6c6e616d  # 'lnam'
kAudioDevicePropertyStreamConfiguration = 0x736c6179  # 'slay'
kAudioDevicePropertyScopeOutput = 0x6f757470  # 'outp'

kAudioObjectPropertyElementMain = 0

# Тип для AudioObjectID / AudioDeviceID — UInt32
AudioObjectID = c_uint32
AudioDeviceID = c_uint32
OSStatus = c_int

# ---------- Структуры ----------

class AudioObjectPropertyAddress(Structure):
    _fields_ = [
        ("mSelector", c_uint32),
        ("mScope", c_uint32),
        ("mElement", c_uint32),
    ]


class AudioBuffer(Structure):
    _fields_ = [
        ("mNumberChannels", c_uint32),
        ("mDataByteSize", c_uint32),
        ("mData", c_void_p),
    ]


class AudioBufferList(Structure):
    _fields_ = [
        ("mNumberBuffers", c_uint32),
        ("mBuffers", AudioBuffer * 1),  # переменная длина — читаем вручную
    ]


# ---------- Загрузка CoreAudio ----------

try:
    _coreaudio = ctypes.CDLL(
        "/System/Library/Frameworks/CoreAudio.framework/Versions/A/CoreAudio"
    )
except OSError:
    # Fallback для старых путей
    try:
        _coreaudio = ctypes.CDLL(
            "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
        )
    except OSError:
        _coreaudio = None


if _coreaudio is not None:
    # Прототипы
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

    # CoreFoundation для работы с CFString
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

# Константа kCFStringEncodingUTF8
_kCFStringEncodingUTF8 = 0x08000100

# Блокировка — чтобы два будильника не переключали устройство одновременно
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
    """Возвращает имя устройства как str или None."""
    if not _HAS_CF:
        return None
    address = _make_address(kAudioDevicePropertyDeviceNameCFString)
    size = _get_property_data_size(device_id, address)
    if size is None or size == 0:
        return None
    # CFStringRef — указатель (8 байт на 64-битной системе)
    cfstr_ref = c_void_p()
    size = c_uint32(ctypes.sizeof(cfstr_ref))
    status = _coreaudio.AudioObjectGetPropertyData(
        device_id, byref(address), 0, None, byref(size), byref(cfstr_ref)
    )
    if status != 0 or not cfstr_ref.value:
        return None
    try:
        # Пытаемся получить указатель на C-строку напрямую
        ptr = _cf.CFStringGetCStringPtr(cfstr_ref.value, _kCFStringEncodingUTF8)
        if ptr:
            return ptr.decode("utf-8", errors="replace")
        # Fallback: копируем в буфер
        length = _cf.CFStringGetLength(cfstr_ref.value)
        buf_size = (length + 1) * 4  # UTF-8 может занимать до 4 байт на символ
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
    """True, если у устройства есть каналы вывода."""
    address = _make_address(
        kAudioDevicePropertyStreamConfiguration,
        scope=kAudioDevicePropertyScopeOutput,
        element=kAudioObjectPropertyElementMain,
    )
    size = _get_property_data_size(device_id, address)
    if size is None or size < ctypes.sizeof(c_uint32):
        return False
    buf = ctypes.create_string_buffer(size)
    got = _get_property_data(device_id, address, size, buf)
    if got is None:
        return False
    try:
        bl = ctypes.cast(buf, POINTER(AudioBufferList)).contents
        num_buffers = bl.mNumberBuffers
        if num_buffers == 0:
            return False
        # Проверяем, что хотя бы у одного буфера есть каналы
        # mBuffers — массив переменной длины, читаем вручную
        base = ctypes.addressof(buf) + ctypes.sizeof(c_uint32)  # после mNumberBuffers
        buffer_size = ctypes.sizeof(AudioBuffer)
        for i in range(num_buffers):
            ab = AudioBuffer.from_address(base + i * buffer_size)
            if ab.mNumberChannels > 0:
                return True
        return False
    except Exception:
        return False


# ---------- Публичные функции ----------

def is_available():
    """True, если CoreAudio загружен и CFString доступен."""
    return _coreaudio is not None and _HAS_CF


def list_output_devices():
    """Возвращает список устройств вывода:
    [{"name": str, "id": int, "is_default": bool}, ...]
    """
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
    """Возвращает AudioDeviceID устройства вывода по умолчанию, либо None."""
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
    """Имя устройства вывода по умолчанию, либо None."""
    dev_id = get_default_output_id()
    if dev_id is None:
        return None
    return _get_device_name(dev_id)


def set_default_output(device_id):
    """Переключает системный вывод на device_id. Возвращает True при успехе."""
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
    """Переключает системный вывод по имени устройства. Возвращает True при успехе."""
    if not name:
        return False
    for dev in list_output_devices():
        if dev["name"] == name:
            return set_default_output(dev["id"])
    return False


def get_device_id_by_name(name):
    """Возвращает AudioDeviceID по имени, либо None."""
    if not name:
        return None
    for dev in list_output_devices():
        if dev["name"] == name:
            return dev["id"]
    return None


def restore_default_output():
    """Возвращает системный вывод на устройство по умолчанию.
    На macOS «по умолчанию» — это то, что выбрано в System Settings.
    Мы не можем «вернуть предыдущее», поэтому просто ставим первое доступное
    или оставляем как есть. Эта функция — no-op, оставлена для семантики.
    """
    return True
