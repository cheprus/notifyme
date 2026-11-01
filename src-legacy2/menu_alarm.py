# src/menu_alarm.py
from AppKit import NSMenu, NSMenuItem

from config import (
    AUTO_CLOSE_PRESETS,
    CONFIG,
    NOTIFY_AFTER_PRESETS,
    NOTIFY_BEFORE_PRESETS,
)


def snooze_presets(notify_before):
    """Пресеты Snooze зависят от Notify Before.
    Snooze <= Notify Before (не больше), чтобы «отложить» не превышало «за сколько до».
    """
    if notify_before <= 5:
        return [1, 2, 3, 5, 10]
    elif notify_before <= 15:
        return [5, 10, 15, 20, 30]
    elif notify_before <= 60:
        return [10, 15, 20, 30, 45]
    else:
        return [15, 30, 45, 60, 120]


def build_notify_before_submenu(controller):
    sub = NSMenu.alloc().init()
    current_min = CONFIG.get("notify_minutes_before", 5)

    for mins in NOTIFY_BEFORE_PRESETS:
        if mins == 0:
            label = "At start"
        elif mins % 60 == 0:
            label = f"{mins // 60}h"
        else:
            label = f"{mins} min"
        prefix = "✓ " if mins == current_min else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{label}", "handleNotifyTime:", ""
        )
        it.setTag_(mins)
        it.setTarget_(controller)
        sub.addItem_(it)

    if current_min not in NOTIFY_BEFORE_PRESETS:
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"✓ {current_min} min (custom)", "handleNotifyTime:", ""
        )
        it.setTag_(current_min)
        it.setTarget_(controller)
        sub.addItem_(it)

    sub.addItem_(NSMenuItem.separatorItem())
    it_custom = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Custom…", "handleNotifyCustom:", ""
    )
    it_custom.setTarget_(controller)
    sub.addItem_(it_custom)

    return sub


def build_notify_after_submenu(controller):
    sub = NSMenu.alloc().init()
    current_min = CONFIG.get("notify_minutes_after", 2)

    for mins in NOTIFY_AFTER_PRESETS:
        if mins == 0:
            label = "At start"
        else:
            label = f"{mins} min"
        prefix = "✓ " if mins == current_min else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{label}", "handleNotifyAfter:", ""
        )
        it.setTag_(mins)
        it.setTarget_(controller)
        sub.addItem_(it)

    if current_min not in NOTIFY_AFTER_PRESETS:
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"✓ {current_min} min (custom)", "handleNotifyAfter:", ""
        )
        it.setTag_(current_min)
        it.setTarget_(controller)
        sub.addItem_(it)

    return sub


def build_auto_close_submenu(controller):
    sub = NSMenu.alloc().init()
    current = CONFIG.get("auto_close_minutes", 15)

    for mins in AUTO_CLOSE_PRESETS:
        prefix = "✓ " if mins == current else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{mins} min", "handleAutoClose:", ""
        )
        it.setTag_(mins)
        it.setTarget_(controller)
        sub.addItem_(it)

    if current not in AUTO_CLOSE_PRESETS:
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"✓ {current} min (custom)", "handleAutoClose:", ""
        )
        it.setTag_(current)
        it.setTarget_(controller)
        sub.addItem_(it)

    return sub


def build_pulse_submenu(controller):
    sub = NSMenu.alloc().init()

    on_secs = CONFIG.get("alarm_sound_on_seconds", 12)
    off_secs = CONFIG.get("alarm_sound_off_seconds", 60)

    on_label = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"Sound: {on_secs} sec", None, ""
    )
    on_label.setEnabled_(False)
    sub.addItem_(on_label)

    for secs in [5, 10, 12, 15, 20, 30]:
        prefix = "✓ " if secs == on_secs else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{secs} sec", "handlePulseOn:", ""
        )
        it.setTag_(secs)
        it.setTarget_(controller)
        sub.addItem_(it)

    sub.addItem_(NSMenuItem.separatorItem())

    off_label = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"Silence: {off_secs} sec", None, ""
    )
    off_label.setEnabled_(False)
    sub.addItem_(off_label)

    for secs in [15, 30, 60, 120, 300]:
        prefix = "✓ " if secs == off_secs else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{secs} sec", "handlePulseOff:", ""
        )
        it.setTag_(secs)
        it.setTarget_(controller)
        sub.addItem_(it)

    return sub


def build_snooze_submenu(controller):
    sub = NSMenu.alloc().init()
    notify_before = CONFIG.get("notify_minutes_before", 5)
    current = CONFIG.get("snooze_minutes", 5)
    presets = snooze_presets(notify_before)

    # Ограничение: snooze <= auto_close
    auto_close = CONFIG.get("auto_close_minutes", 15)
    presets = [m for m in presets if m <= auto_close]

    # Если текущее значение не в пресетах, но допустимо — показываем как custom
    if current > auto_close:
        current = auto_close

    for mins in presets:
        prefix = "✓ " if mins == current else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{mins} min", "handleSnoozeTime:", ""
        )
        it.setTag_(mins)
        it.setTarget_(controller)
        sub.addItem_(it)

    if current not in presets:
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"✓ {current} min (custom)", "handleSnoozeTime:", ""
        )
        it.setTag_(current)
        it.setTarget_(controller)
        sub.addItem_(it)

    return sub
