```markdown
# NotifyMe

Menu bar app for macOS that tracks upcoming calendar events and reminds you before they start.

## Features

- Menu bar icon with countdown to the next event
- Alarm window a few minutes before the meeting, on top of all windows
- Quick access to meeting link (`Location`) and tracker (`URL`)
- Copy selected events to clipboard
- Configurable timezone, sound, audio output, and target calendar
- Works with any macOS calendar out of the box

## Install

1. Download `NotifyMe.dmg`.
2. Drag `NotifyMe.app` to `/Applications`.
3. Launch it. macOS will ask for Calendar access — allow it.
4. The hourglass icon appears in the menu bar.

## Usage

- Click the icon in the menu bar to see upcoming events.
- Click an event row to open a card with all details.
- Click the checkbox to select events, then use the alarm window or card to copy them.
- Settings:
  - Calendar — where new events are created. `(default)` uses the system default calendar.
  - Timezone (display) — timezone for menu, alarm, card. `Local` uses the OS timezone.
  - Timezone (copy) — timezone used only when copying events to the clipboard.
  - Notify Before — how many minutes before the meeting to show the alarm. Includes `Custom…`.
  - Sound — alarm sound.
  - Output — audio output device.

## Settings file

Settings are stored in `~/.notifyme/config.json`.

Key options:

| Key | Description |
|---|---|
| `target_calendar_name` | Calendar for new events. Empty = system default. |
| `display_timezone` | Timezone for display. `Local` = OS timezone. |
| `copy_timezone` | Timezone for clipboard. |
| `notify_minutes_before` | Minutes before the event to show the alarm. |
| `sound_file` | Path to the alarm sound. |
| `sound_output_device` | Audio output device, or `Default`. |

## Troubleshooting

No icon in the menu bar.
Open System Settings → Menu Bar → Allow in the Menu Bar and enable NotifyMe. On macOS Tahoe, accessory-app icons may be hidden if the menu bar is full.

Calendar permission was reset after rebuild.
Run:
```bash
tccutil reset Calendar com.chep.notifyme
```
Then relaunch and allow access again.

Alarm rings at the wrong time.
Check `notify_minutes_before` in Settings → Notify Before.

Events are created in the wrong calendar.
Check Settings → Calendar. If the configured calendar doesn't exist, NotifyMe falls back to the system default.

## For developers

### Requirements

- macOS 13+ (tested on macOS 26 Tahoe)
- Python 3.13+
- Xcode Command Line Tools
- pyinstaller

### Build

```bash
./build.sh
```

### Code signing and TCC

NotifyMe needs Calendar access. macOS (TCC) binds this permission to the app's code signature.

Ad-hoc signing (`codesign --sign -`) generates a new identity on every build, so macOS forgets the Calendar permission after each `./build.sh`.

Use a stable certificate instead (self-signed is fine):

1. Check available identities:
   ```bash
   security find-identity -p codesigning
   ```
2. Create a self-signed Code Signing certificate in Keychain Access if needed.
3. Set `CODESIGN_IDENTITY` in `build.sh` to your certificate name.
4. Reset TCC once and re-grant:
   ```bash
   tccutil reset Calendar com.chep.notifyme
   ./build.sh
   ```

After that, permissions persist across rebuilds.

### Project structure

```
.
├── build.sh
├── README.md
├── requirements.txt
├── pyproject.toml
├── assets/
│   ├── entitlements.plist
│   └── myicon.icns
├── scripts/
│   └── Install_NotifyMe.command
└── src/
    ├── app.py
    ├── status_bar.py
    ├── menu_item_view.py
    ├── dialogs.py
    ├── event_card.py
    ├── add_event_window.py
    ├── calendar_service.py
    ├── calendar_icon.py
    ├── ui_utils.py
    ├── audio_output.py
    ├── config.py
    └── state_manager.py
```

### Debugging

Logs:

- `/tmp/notifyme.log`
- `/tmp/notifyme_debug.log`

Run from terminal:

```bash
/Applications/NotifyMe.app/Contents/MacOS/NotifyMe
```

Check `audio_output` in bundle:

```bash
find /Applications/NotifyMe.app -name "audio_output*"
```

### Customization

Add environment-specific values to `~/.notifyme/config.json`:

```json
{
    "target_calendar_name": "Work",
    "work_calendar_hints": ["work", "event", "job"],
    "custom_tracker_domains": ["tracker.example.com"],
    "custom_meeting_domains": ["meet.example.com"],
    "tracker_base_url": "https://tracker.example.com/issues/"
}
```

- `target_calendar_name` — calendar for new events. Empty → system default.
- `work_calendar_hints` — substrings to highlight "work" events.
- `custom_tracker_domains` — tracker domains (classified as `URL`).
- `custom_meeting_domains` — meeting domains (classified as `Location`).
- `tracker_base_url` — base URL to recover links from `#123`.

## License

MIT
```
