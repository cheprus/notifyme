# src/strings.py
"""UI-строки. Плоские константы, чтобы легко грепать и не плодить магию.

Правило: сюда идёт только то, что реально отображается пользователю.
Логи, debug-сообщения и ключи конфига — не здесь.
"""

# ---------- Общие ----------
BTN_CLOSE = "❌ Закрыть"
BTN_SAVE = "Save"
BTN_CANCEL = "Cancel"

# ---------- Add event window ----------
ADD_EVENT_TITLE = "New Event"
ADD_EVENT_LBL_TITLE = "Title:"
ADD_EVENT_LBL_START = "Start:"
ADD_EVENT_LBL_DURATION = "Duration (min):"
ADD_EVENT_LBL_LOCATION = "Location (встреча):"
ADD_EVENT_LBL_URL = "URL (трекер):"
ADD_EVENT_LBL_NOTES = "Notes:"
ADD_EVENT_BTN_PASTE = "📋 Paste from Clipboard"
ADD_EVENT_ERR_TITLE = "Failed to save event"
ADD_EVENT_ERR_BODY = "Error: {error}\n\nSee /tmp/notifyme_debug.log for details."

# ---------- Event card ----------
CARD_TITLE_PREFIX = "Event — {calendar}"
CARD_TITLE_FALLBACK = "Event"
CARD_LBL_TITLE = "Title"
CARD_LBL_CALENDAR = "Calendar"
CARD_LBL_START = "Start"
CARD_LBL_END = "End"
CARD_LBL_LOCATION = "Location"
CARD_LBL_URL = "URL"
CARD_LBL_NOTES = "Notes"
CARD_BTN_CLOSE = "Закрыть"
CARD_BTN_COPY = "Копировать"
CARD_BTN_OPEN_MEETING = "Открыть встречу"
CARD_BTN_OPEN_TRACKER = "Открыть трекер"

# ---------- Alarm dialog ----------
ALARM_BTN_OPEN_MEETING = "🔗 Открыть встречу"
ALARM_BTN_COPY = "📋 Копировать"
ALARM_BTN_CLOSE = "❌ Закрыть"
ALARM_BTN_SNOOZE = "⏰ Отложить {minutes} мин"
ALARM_BTN_MUTE = "🔇 Заглушить"
ALARM_BTN_MUTED = "🔇 Заглушено"

# ---------- Copy format ----------
COPY_EVENT_HEADER = "📅 Event: {title}"
COPY_LINK = "🔗 {url}"
COPY_LOCATION = "📍 {location}"
COPY_NOTES = "📝 {notes}"

# ---------- Status bar / menu ----------
MENU_NEW_EVENT = "➕ New event"
MENU_OPEN_CALENDAR = "📅 Open Calendar"
MENU_QUIT = "Quit"
MENU_NO_EVENTS_TODAY = "No events today"
MENU_DND_UNTIL = "🔕 DND until {time}"
MENU_DND_UNTIL_END = "🔕 DND until current event ends"
MENU_SECTION_ONGOING = "— Ongoing —"
MENU_SECTION_UPCOMING = "— Upcoming —"
MENU_SECTION_FINISHED = "— Finished —"
MENU_SECTION_TOMORROW = "— Tomorrow —"
MENU_SECTION_NEXT_7_DAYS = "— Next 7 Days —"
MENU_MORE_EVENTS = "... and {n} more"
MENU_ROW_UNTITLED = "Untitled"
MENU_CHECK_ON = "☑"
MENU_CHECK_OFF = "☐"

# ---------- Quit confirm ----------
QUIT_TITLE = "Quit NotifyMe?"
QUIT_BODY = "Alarms will stop working until you launch the app again."
QUIT_BTN_QUIT = "Quit"
QUIT_BTN_CANCEL = "Cancel"

# ---------- Settings menu ----------
SETTINGS_TITLE = "⚙️ Settings"
SETTINGS_HDR_ALARM = "── Alarm ──"
SETTINGS_HDR_CALENDAR = "── Calendar ──"
SETTINGS_HDR_SYSTEM = "── System ──"
SETTINGS_NOTIFY_BEFORE = "⏱ Notify Before"
SETTINGS_NOTIFY_AFTER = "⏱ Notify After (start)"
SETTINGS_SNOOZE = "⏰ Snooze"
SETTINGS_AUTO_CLOSE = "⏲ Auto-close Alarm"
SETTINGS_PULSE = "🔔 Alarm Pulse"
SETTINGS_SOUND = "🔊 Sound"
SETTINGS_OUTPUT = "🔈 Output"
SETTINGS_CALENDAR = "📅 Calendar"
SETTINGS_CALENDAR_DEFAULT = "(default)"
SETTINGS_TZ_DISPLAY = "🌍 Timezone (display)"
SETTINGS_TZ_COPY = "📋 Timezone (copy)"
SETTINGS_HOTKEY_OK = "✓ ⌨️ Hotkey Cmd+Ctrl+N"
SETTINGS_HOTKEY_NEEDS_AX = "⌨️ Hotkey Cmd+Ctrl+N — Needs Accessibility"
SETTINGS_HOTKEY_HINT = "   → System Settings → Privacy → Accessibility"
SETTINGS_CLEAR_HISTORY = "🔄 Clear History"
SETTINGS_INCLUDE_NOTES_ON = "✓ 📝 Include Notes in Copy"
SETTINGS_INCLUDE_NOTES_OFF = "  📝 Include Notes in Copy"
SETTINGS_CHECK = "✓ "
SETTINGS_UNCHECK = "   "

# ---------- Notify Custom dialog ----------
NOTIFY_CUSTOM_TITLE = "Notify Before"
NOTIFY_CUSTOM_BODY = "Minutes before the event (0–1440):"
NOTIFY_CUSTOM_OK = "OK"
NOTIFY_CUSTOM_CANCEL = "Cancel"

# ---------- Alarm presets labels ----------
PRESET_AT_START = "At start"
PRESET_MIN = "{n} min"
PRESET_HOUR = "{n}h"
PRESET_MIN_CUSTOM = "{n} min (custom)"
PRESET_CUSTOM_ELLIPSIS = "Custom…"
PULSE_ON_LABEL = "Sound: {n} sec"
PULSE_OFF_LABEL = "Silence: {n} sec"
