# src/hotkeys.py
from typing import Any

import objc
from AppKit import (
    NSEvent,
    NSEventMaskKeyDown,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
)
from Foundation import NSObject

try:
    from ApplicationServices import AXIsProcessTrusted
    _HAS_AX = True
except ImportError:
    AXIsProcessTrusted = None
    _HAS_AX = False

try:
    from Quartz import CGPreflightPostEventAccess
    _HAS_CG = True
except ImportError:
    CGPreflightPostEventAccess = None
    _HAS_CG = False

# _RETAINED хранит HotkeyMonitor, чтобы NSEvent его не собрал GC
_RETAINED: dict[str, Any] = {}


class HotkeyMonitor(NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(HotkeyMonitor, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def handleEvent_(self, event):
        try:
            mods = event.modifierFlags() & 0xFFFF0000
            chars = (event.charactersIgnoringModifiers() or "").lower()
            required = NSEventModifierFlagCommand | NSEventModifierFlagControl
            if chars == "n" and (mods & required) == required and self._callback:
                self._callback(None)
        except Exception as e:
            print(f"[DEBUG] hotkey handle error: {e}", flush=True)


def is_accessibility_granted():
    if _HAS_CG:
        try:
            if CGPreflightPostEventAccess():
                return True
        except Exception:
            pass
    if _HAS_AX:
        try:
            return bool(AXIsProcessTrusted())
        except Exception:
            pass
    return False


def install_hotkey(callback):
    monitor = HotkeyMonitor.alloc().initWithCallback_(callback)
    try:
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, monitor.handleEvent_
        )
        _RETAINED["monitor"] = monitor
        print("[DEBUG] Global hotkey Cmd+Ctrl+N installed", flush=True)
        return monitor
    except Exception as e:
        print(f"[DEBUG] install_hotkey failed: {e}", flush=True)
        return None
