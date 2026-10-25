# NotifyMe

A macOS menu bar application which tracks upcoming calendar events and sends reminders.

## Features
- Animated hourglass icon in the menu bar.
- Color-coded urgency for upcoming events (from red to blue).
- Pop-up reminders 5 minutes before an event starts (auto-dismisses after 15 minutes).
- List of today's events and a 7-day forecast.
- Melodic notification sound.

## Installation
1. Download `NotifyMe.dmg`.
2. Open the DMG and run `Install_NotifyMe.command`.
3. If macOS blocks the script, go to System Settings -> Privacy & Security and click "Open Anyway".

## Usage
The app is controlled via the `notifyme` command (requires a symlink in `/usr/local/bin`).

- `notifyme` — start the app.
- `notifyme stop` — stop the app.
- `notifyme restart` — restart the app.

## Development
To rebuild the app, install it to `/Applications`, and create a DMG, run:
`./build.sh`
