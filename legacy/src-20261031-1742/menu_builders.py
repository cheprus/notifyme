# src/menu_builders.py
import os

from AppKit import NSMenu, NSMenuItem

from alarm_utils import _get_audio_outputs
from calendar_service import list_calendars
from config import (
    AVAILABLE_SOUNDS,
    AVAILABLE_TIMEZONES,
    CONFIG,
)
from menu_alarm import (
    build_auto_close_submenu,
    build_notify_after_submenu,
    build_notify_before_submenu,
    build_pulse_submenu,
    build_snooze_submenu,
)


def build_timezone_submenu(controller, current, action_selector):
    sub = NSMenu.alloc().init()

    flat = ["Local", "UTC"]
    for tz in flat:
        prefix = "✓ " if tz == current else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{tz}", action_selector, ""
        )
        it.setRepresentedObject_(tz)
        it.setTarget_(controller)
        sub.addItem_(it)

    if current and current not in flat:
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"✓ {current}", action_selector, ""
        )
        it.setRepresentedObject_(current)
        it.setTarget_(controller)
        sub.addItem_(it)

    sub.addItem_(NSMenuItem.separatorItem())

    # mypy: regions: dict[str, list[str]]
    regions: dict[str, list[str]] = {}
    for tz in AVAILABLE_TIMEZONES:
        if tz in ("Local", "UTC") or tz == current:
            continue
        if "/" in tz:
            region = tz.split("/", 1)[0]
        else:
            region = "Other"
        regions.setdefault(region, []).append(tz)

    preferred = ["Europe", "Asia", "America", "Africa", "Australia", "Pacific", "Atlantic", "Indian"]
    ordered = []
    for r in preferred:
        if r in regions:
            ordered.append(r)
    for r in sorted(regions.keys()):
        if r not in ordered:
            ordered.append(r)

    for region in ordered:
        region_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{region} ({len(regions[region])})", None, ""
        )
        region_sub = NSMenu.alloc().init()
        for tz in regions[region]:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                tz, action_selector, ""
            )
            it.setRepresentedObject_(tz)
            it.setTarget_(controller)
            region_sub.addItem_(it)
        region_item.setSubmenu_(region_sub)
        sub.addItem_(region_item)

    return sub


def build_settings_menu(controller, is_accessibility_granted=None, has_hotkeys=False):
    settings_menu = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⚙️ Settings", None, "")
    settings_sub = NSMenu.alloc().init()

    def add_header(title):
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
        it.setEnabled_(False)
        settings_sub.addItem_(it)

    # ===== Alarm =====
    add_header("── Alarm ──")

    time_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⏱ Notify Before", None, "")
    time_item.setSubmenu_(build_notify_before_submenu(controller))
    settings_sub.addItem_(time_item)

    after_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⏱ Notify After (start)", None, "")
    after_item.setSubmenu_(build_notify_after_submenu(controller))
    settings_sub.addItem_(after_item)

    snooze_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⏰ Snooze", None, "")
    snooze_item.setSubmenu_(build_snooze_submenu(controller))
    settings_sub.addItem_(snooze_item)

    auto_close_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("⏲ Auto-close Alarm", None, "")
    auto_close_item.setSubmenu_(build_auto_close_submenu(controller))
    settings_sub.addItem_(auto_close_item)

    pulse_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔔 Alarm Pulse", None, "")
    pulse_item.setSubmenu_(build_pulse_submenu(controller))
    settings_sub.addItem_(pulse_item)

    sound_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔊 Sound", None, "")
    sound_sub = NSMenu.alloc().init()
    current_sound = os.path.basename(CONFIG.get("sound_file", ""))
    for snd in AVAILABLE_SOUNDS:
        prefix = "✓ " if snd == current_sound else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{snd}", "playSoundPreview:", ""
        )
        it.setTarget_(controller)
        sound_sub.addItem_(it)
    sound_item.setSubmenu_(sound_sub)
    settings_sub.addItem_(sound_item)

    out_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🔈 Output", None, "")
    out_sub = NSMenu.alloc().init()
    current_out = CONFIG.get("sound_output_device", "Default")
    try:
        outputs = _get_audio_outputs()
    except Exception:
        outputs = ["Default"]
    for dev in outputs:
        prefix = "✓ " if dev == current_out else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(f"{prefix}{dev}", "handleAudioOutput:", "")
        it.setRepresentedObject_(dev)
        it.setTarget_(controller)
        out_sub.addItem_(it)
    out_item.setSubmenu_(out_sub)
    settings_sub.addItem_(out_item)

    settings_sub.addItem_(NSMenuItem.separatorItem())

    # ===== Calendar =====
    add_header("── Calendar ──")

    cal_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📅 Calendar", None, "")
    cal_sub = NSMenu.alloc().init()
    current_cal = CONFIG.get("target_calendar_name", "") or ""
    try:
        cals = list_calendars(controller.app.store) if controller.app.store else []
        cal_names = [c.get("title") for c in cals if c.get("title")]
    except Exception:
        cal_names = []

    if current_cal and current_cal not in cal_names:
        current_cal = ""

    prefix = "✓ " if not current_cal else "   "
    it_default = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"{prefix}(default)", "handleCalendar:", ""
    )
    it_default.setRepresentedObject_("")
    it_default.setTarget_(controller)
    cal_sub.addItem_(it_default)

    for cal_name in cal_names:
        prefix = "✓ " if cal_name == current_cal else "   "
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"{prefix}{cal_name}", "handleCalendar:", ""
        )
        it.setRepresentedObject_(cal_name)
        it.setTarget_(controller)
        cal_sub.addItem_(it)

    cal_item.setSubmenu_(cal_sub)
    settings_sub.addItem_(cal_item)

    tz_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("🌍 Timezone (display)", None, "")
    current_tz = CONFIG.get("display_timezone", "Local")
    tz_item.setSubmenu_(build_timezone_submenu(controller, current_tz, "handleDisplayTimezone:"))
    settings_sub.addItem_(tz_item)

    tz_copy_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📋 Timezone (copy)", None, "")
    current_copy_tz = CONFIG.get("copy_timezone", "Local")
    tz_copy_item.setSubmenu_(build_timezone_submenu(controller, current_copy_tz, "handleCopyTimezone:"))
    settings_sub.addItem_(tz_copy_item)

    settings_sub.addItem_(NSMenuItem.separatorItem())

    # ===== System =====
    add_header("── System ──")

    if has_hotkeys:
        ax_granted = is_accessibility_granted() if is_accessibility_granted else False
        if ax_granted:
            hotkey_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "✓ ⌨️ Hotkey Cmd+Ctrl+N", None, ""
            )
            hotkey_item.setEnabled_(False)
            settings_sub.addItem_(hotkey_item)
        else:
            hotkey_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "⌨️ Hotkey Cmd+Ctrl+N — Needs Accessibility",
                "openAccessibilitySettings:", ""
            )
            hotkey_item.setTarget_(controller)
            settings_sub.addItem_(hotkey_item)

            hint_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "   → System Settings → Privacy → Accessibility", None, ""
            )
            hint_item.setEnabled_(False)
            settings_sub.addItem_(hint_item)

    clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "🔄 Clear History", "clearHistory:", ""
    )
    clear_item.setTarget_(controller)
    settings_sub.addItem_(clear_item)

    notes_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"{'✓' if CONFIG.get('include_notes_in_copy', False) else '  '} 📝 Include Notes in Copy",
        "toggleIncludeNotes:", ""
    )
    notes_item.setTarget_(controller)
    settings_sub.addItem_(notes_item)

    settings_menu.setSubmenu_(settings_sub)
    return settings_menu
