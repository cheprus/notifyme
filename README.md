# NotifyMe

macOS menu bar app for upcoming calendar events with reminders.

## Features

- Menu bar countdown to the next event; alarm window on top with Snooze.
- Event card: title, calendar, start/end, location, URL, notes.
- Checkbox on each event: **click → selection copied to clipboard** (all selected).
- Two color stripes per row: time urgency + calendar importance; work events bold.
- Settings window (Alarm / Conferences / Calendar / System / About). Changes applied live.
- Separate timezones for display and clipboard.
- Configurable sound, audio output, target calendar.
- Global hotkey `Cmd+Ctrl+N` → New event from clipboard.
- DND until current event ends.
- CLI: `notifyme start|stop|restart|refresh`.

## Install

### DMG

1. Open `NotifyMe.dmg`, drag `NotifyMe.app` to `/Applications`.
2. Launch, allow Calendar access. Hourglass icon appears in menu bar.

Python is bundled; nothing else to install.

### From source

Requires Python 3.13 (python.org) and Xcode Command Line Tools.

```bash
make install-dev
make release   # build + sign + install to /Applications + start + dmg
```

## Usage

Click the menu bar icon. Each row: checkbox, time, title, countdown, stripes.

- **Click row** → event card.
- **Click checkbox** → select event; selection auto-copied to clipboard.
- **`📋 Копировать выбранные (N)`** — appears when selection is non-empty (manual re-copy).
- **`⚙️ Settings`** (`Cmd+,`) → settings window.
- **`🔕 DND ...`** — toggle DND until current event ends.
- **`📅 Open Calendar`** — launch Calendar.app.
- **`Quit`** (`Cmd+Q`).

### Settings

- **Alarm**: Notify Before/After, Snooze, Auto-close, Pulse ON/OFF, Sound (with Preview toggle), Output (device + `↻` refresh).
- **Conferences**: tracker / meeting domain lists with `+`, `−`, `Reset to known`, `Undo`.
- **Calendar**: target calendar, display/copy timezone, work calendar hints.
- **System**: hotkey status + Open Accessibility, DND toggle, Include Notes, Clear History / Clear Last, Export / Import / Reset, Open log, Restart.
- **About**: name, version, author, license, home URL.

All settings auto-saved (debounce 300 ms) and applied without restart.

## Hotkey

`Cmd+Ctrl+N` requires Accessibility:

1. Settings → System → **Open Accessibility Settings…**
2. System Settings → Privacy & Security → Accessibility → enable NotifyMe.
3. Settings → System → **Restart NotifyMe**.

If the hotkey doesn't fire, ensure focus is not in Finder (it consumes `Cmd+Ctrl+N` to create a folder).

## CLI

```bash
notifyme start     # launch /Applications/NotifyMe.app (or activate if running)
notifyme stop      # kill all processes; refreshes menu bar
notifyme restart   # stop + start
notifyme refresh   # refresh menu bar (remove phantom icons after kill -9)
notifyme --add-event
```

## Config file

`~/.notifyme/config.json` — auto-managed by Settings. Edit only if you know what you do. `~/.notifyme/state.json` — shown event ids for today.

## Troubleshooting

**No menu bar icon.** System Settings → Menu Bar → enable NotifyMe.

**Calendar permission lost after rebuild.** Use a stable code signing certificate (see below) instead of ad-hoc. Reset once: `tccutil reset Calendar com.chep.notifyme`.

**URL shows `%20` / `%D0%9C`.** EventKit sometimes returns `URL - Title` as one string. Fixed in v1.0.0 via `classify.clean_url`. Rebuild if you're on older code.

**Phantom icon after `kill -9`.** Run `notifyme refresh`.

**Hotkey does not work.** See "Hotkey". Requires Accessibility, and restart after granting.

**Sound preview plays in wrong device.** In Alarm tab, pick Output and press `↻` after plugging/unplugging devices. On Preview the system default is temporarily switched and restored on stop.

## Code signing

For persistent Calendar permission across rebuilds, use a stable certificate `NotifyMe Dev` (Keychain Access → Certificate Assistant → Create a Certificate → Code Signing, self-signed). Then `security find-identity -p codesigning` should list it. Set `CODESIGN_IDENTITY = "NotifyMe Dev"` in `scripts/sign.py` and `scripts/install.py`.

Ad-hoc (`CODESIGN_IDENTITY = "-"`) works but TCC forgets Calendar permission after each `make release`.

## Build targets

```bash
make ci           # clean + ruff + mypy + pytest
make build        # pyinstaller → dist/NotifyMe.app
make sign         # build + symlinks + codesign dist/
make install-app  # sign + copy to /Applications + start
make dmg          # sign + NotifyMe.dmg
make release      # build + sign + install-app + dmg
```

`assets/entitlements.plist` must contain both calendar keys (`calendars` and `calendars.full`).

## License

MIT
