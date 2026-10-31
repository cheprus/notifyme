# NotifyMe

macOS menu bar app for upcoming calendar events with reminders.

## Features

- Menu bar countdown to the next event
- Alarm window on top of all windows, with Snooze
- Event card on click: Title, Calendar, Start, End, Location, URL, Notes
- Copy events (checkbox, alarm, card)
- Two color stripes per row: time urgency and calendar importance
- Work events highlighted (bold title, bright stripe)
- Separate timezones for display and clipboard
- Configurable sound, audio output, target calendar
- Notify Before: presets + `Custom…`
- Global hotkey `Cmd+Ctrl+N` → New event from clipboard (requires Accessibility)
- Do Not Disturb until the current event ends

## Install

### For users (DMG)

1. Open `NotifyMe.dmg`.
2. Drag `NotifyMe.app` to `/Applications`.
3. Launch. Allow Calendar access.
4. Hourglass icon appears in menu bar.

**Python is not required.** The app bundles its own Python runtime.

### For developers (build from source)

1. Install **Python 3.13** from [python.org](https://www.python.org/downloads/macos/).
2. Install Xcode Command Line Tools:
   ```bash
   xcode-select --install
   ```
3. Install dependencies:
   ```bash
   make install-dev
   ```
4. Create a code signing certificate (see below).
5. Build, sign and install:
   ```bash
   make release
   ```
   Builds `dist/NotifyMe.app`, signs it, copies to `/Applications`, starts the app, builds `NotifyMe.dmg`.

## Usage

- Click icon to see events. Each row: checkbox, time, title, countdown, two stripes.
- Click row to open event card.
- Click checkbox to select events for copying.
- Press `Cmd+Ctrl+N` from anywhere to create a new event from clipboard.
- `Settings`:
  - **Calendar** — new events calendar. `(default)` = system default.
  - **Timezone (display)** — menu, alarm, card. `Local` = OS.
  - **Timezone (copy)** — clipboard only.
  - **Notify Before** — minutes before alarm. Includes `Custom…`.
  - **Sound** — alarm sound.
  - **Output** — audio device.
  - **Hotkey Cmd+Ctrl+N** — shows `Needs Accessibility` until granted.
- **DND until current event ends** — suppresses alarms until the ongoing meeting finishes.

## Hotkey

`Cmd+Ctrl+N` works only if Accessibility is granted:

1. `⚙️ Settings → ⌨️ Hotkey Cmd+Ctrl+N — Needs Accessibility` → click.
2. System Settings → Privacy & Security → Accessibility opens.
3. Enable `NotifyMe` (or add `/Applications/NotifyMe.app` with `+`).
4. **Quit and relaunch NotifyMe.**
5. `⚙️ Settings` shows `✓ ⌨️ Hotkey Cmd+Ctrl+N`.

If Accessibility is granted but the hotkey still does not fire, check that the focus is not in Finder (where `Cmd+Ctrl+N` creates a new folder and consumes the event). Try in TextEdit.

## Settings file

`~/.notifyme/config.json`:

| Key | Description |
|---|---|
| `target_calendar_name` | Calendar for new events. Empty = system default |
| `display_timezone` | Display timezone. `Local` = OS |
| `copy_timezone` | Clipboard timezone |
| `notify_minutes_before` | Minutes before alarm |
| `sound_file` | Alarm sound path |
| `sound_output_device` | Audio device or `Default` |
| `work_calendar_hints` | Substrings to detect work calendars |
| `custom_tracker_domains` | Tracker domains (→ `URL`) |
| `custom_meeting_domains` | Meeting domains (→ `Location`) |
| `tracker_base_url` | Base URL for `#123` links |
| `dnd_until` | ISO datetime until DND is active (or `null`) |

## Diagnostics

Run from terminal to see all logs and tracebacks in the console:

```bash
/Applications/NotifyMe.app/Contents/MacOS/NotifyMe
```

For `New event` window:

```bash
/Applications/NotifyMe.app/Contents/MacOS/NotifyMe --add-event
```

System log stream (macOS unified log):

```bash
log stream --predicate 'process == "NotifyMe"' --info --debug
```

App logs on disk:

- `/tmp/notifyme.log` — stdout from `open -a` launch
- `/tmp/notifyme_debug.log` — Calendar and AppleScript debug output

Audio devices:

```bash
cd src && python3 -c "import audio_output; print(audio_output.list_output_devices())"
```

`audio_output` in bundle:

```bash
find /Applications/NotifyMe.app -name "audio_output*"
```

Accessibility state:

```bash
cd src && python3 -c "from hotkeys import is_accessibility_granted; print(is_accessibility_granted())"
```

## Troubleshooting

**No menu bar icon.** System Settings → Menu Bar → Allow in the Menu Bar → enable NotifyMe.

**Calendar permission reset after rebuild.** `tccutil reset Calendar com.chep.notifyme`, relaunch, allow. See "Code signing" below.

**Alarm at wrong time.** Check `notify_minutes_before`.

**Events in wrong calendar.** Check Settings → Calendar. Missing calendar falls back to system default.

**Card / New event does not open.** Run from terminal (see Diagnostics) — traceback appears in stdout.

**Hotkey does not work.** See "Hotkey" section. Requires Accessibility. After granting, quit and relaunch NotifyMe. If still failing on macOS 26.1, try dragging `NotifyMe.app` into the Accessibility list window instead of using `+`.

**Output list empty.** See Diagnostics → Audio devices.

## For developers

### Build

```bash
make ci          # clean + ruff + mypy + pytest (no build)
make build       # pyinstaller → dist/NotifyMe.app (no sign)
make sign        # build + restore Python.framework symlinks + codesign dist/
make install-app # sign + copy to /Applications + sign + start
make dmg         # sign + create NotifyMe.dmg
make release     # build + sign + install-app + dmg
```

Сборка идёт через `scripts/`:

- `scripts/build.py` — pyinstaller + патч `Info.plist` (calendar usage descriptions).
- `scripts/sign.py` — восстанавливает канонические симлинки `Python.framework` (pyinstaller их теряет — иначе `codesign` ругается «bundle format is ambiguous») и подписывает `dist/`.
- `scripts/install.py` — копирует подписанный бандл в `/Applications`, поправляет симлинки для `python3.13`/`base_library.zip`/`audio_output.py`/`sounds/`, подписывает внутренние `.so`/`.dylib` и бандл.
- `scripts/dmg.py` — собирает DMG из `dist/`.

`assets/entitlements.plist` должен содержать **оба** ключа:

```xml
<key>com.apple.security.personal-information.calendars</key><true/>
<key>com.apple.security.personal-information.calendars.full</key><true/>
```

Без `.full` на macOS 14+ приложение не сможет создавать события.

### Code signing certificate

TCC binds the Calendar permission to the app's code signature. Ad-hoc signing (`codesign --sign -`) generates a new identity on every build, so macOS forgets the permission after each `make release`. Use a stable certificate instead.

**Option A — Keychain Access (GUI)**

1. Open **Keychain Access → Certificate Assistant → Create a Certificate…**
2. Name: `NotifyMe Dev`
3. Identity Type: **Self Signed Root**
4. Certificate Type: **Code Signing**
5. Create.
6. Verify:
   ```bash
   security find-identity -p codesigning
   ```
   You should see `"NotifyMe Dev"`.

Trust is **not required** for local `codesign`. Trust is only needed for Gatekeeper when distributing the `.app` to other machines.

**Option B — openssl (scripted)**

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout /tmp/notifyme.key -out /tmp/notifyme.crt \
  -subj "/CN=NotifyMe Dev" \
  -addext "basicConstraints=critical,CA:false" \
  -addext "keyUsage=critical,digitalSignature" \
  -addext "extendedKeyUsage=critical,codeSigning"

openssl pkcs12 -export -legacy -out /tmp/notifyme.p12 \
  -inkey /tmp/notifyme.key -in /tmp/notifyme.crt -passout pass:notifyme

security import /tmp/notifyme.p12 -k ~/Library/Keychains/login.keychain-db \
  -P notifyme -T /usr/bin/codesign

rm -f /tmp/notifyme.{key,crt,p12}
```

`extendedKeyUsage=critical,codeSigning` is required, otherwise `codesign` won't see the certificate. `-legacy` in `pkcs12` is required for `security import`.

**Configure**

Идентификатор задаётся в двух местах — держите их синхронными:

- `scripts/sign.py` → `CODESIGN_IDENTITY`
- `scripts/install.py` → `CODESIGN_IDENTITY`

Затем сбросьте TCC один раз:

```bash
tccutil reset Calendar com.chep.notifyme
make release
```

Разрешения сохраняются между пересборками.

Если пропустить сертификат и поставить `CODESIGN_IDENTITY="-"` (ad-hoc) — приложение работает, но macOS забывает Calendar-разрешение после каждой пересборки.

### Project structure

```
.
├── Makefile
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── assets/
│   ├── entitlements.plist
│   ├── myicon.icns
│   └── sounds/
├── scripts/
│   ├── build.py       # pyinstaller + patch Info.plist
│   ├── sign.py        # symlinks + codesign dist/
│   ├── install.py     # copy to /Applications + codesign
│   ├── dmg.py         # create-dmg
│   └── Install_NotifyMe.command
├── tests/
│   ├── test_dependencies.py
│   ├── test_logic.py
│   └── test_logic_extra.py
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
    ├── time_utils.py
    ├── color_utils.py
    ├── clipboard_utils.py
    ├── audio_output.py
    ├── hotkeys.py
    ├── config.py
    └── state_manager.py
```

### Customization

Environment-specific values in `~/.notifyme/config.json`:

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
- `work_calendar_hints` — substrings to highlight work events.
- `custom_tracker_domains` — tracker domains (→ `URL`).
- `custom_meeting_domains` — meeting domains (→ `Location`).
- `tracker_base_url` — base URL to recover `#123` links.

## License

MIT
