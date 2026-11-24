# TODO

## Settings
- **Target calendar for New event**: сейчас `CONFIG["target_calendar_name"]` есть, но в Settings → Calendar попап показывает список из `list_calendars(store)`. Если список пуст (EventKit не вернул) — попап пустой. Проверить, что вкладка Calendar подгружает календари корректно, и что `create_event_via_applescript` использует выбранный (fallback на default). Также добавить в New event окно выбор календаря (не только в Settings).

## Audio
- **Output override глобальный**: `play_on_device` в `audio_output.py` переключает **системный default output** (`kAudioHardwarePropertyDefaultOutputDevice`) через `set_default_output_id`, играет `NSSound`, возвращает обратно. Пока играет — **все** приложения (Zoom, Music, YouTube) переезжают на выбранное устройство. Это влияет на другие приложения. Впервые вижу, чтобы приложение глобально меняло вывод — это by design macOS, но для alarm/preview это **заметно**.
  - **Фикс**: HAL Output AudioUnit или `AVAudioEngine` с привязкой к устройству **без** смены системного дефолта. Пробовали HAL — `CurrentDevice` не срабатывал на всех устройствах. Попробовать снова, но:
    - не трогать `kAudioOutputUnitProperty_EnableIO` для output (только input);
    - `StreamFormat` в **нативный** формат устройства (sample rate 48k, interleaved), не 44.1k;
    - `SetRenderCallback` в `Global` (0), не `Input` (1);
    - проверить `AudioUnitGetProperty(CurrentDevice)` после `SetProperty`.
  - **Альтернатива**: `AVAudioEngine` + `AVAudioOutputNode.auAudioUnit` (raw pointer через `objc.pyobjc_id`) + `AudioUnitSetProperty(CurrentDevice)`. Пробовали — не сработало. Вернуться, если найден способ.
  - **Fallback**: `afplay -d <device>` — `afplay` **не** поддерживает выбор устройства. `SwitchAudioSource` (brew) — переключает **системный** дефолт (то же самое). Значит — только HAL/AVAudioEngine.

## AI
- Settings → вкладка AI: api_key, model, system prompt, reminders.
- `src/ai.py` + `tests/test_ai.py`.
- Меню → Ask AI…

## CLI
- `notifyme --settings` / `--about` / `--version`

## Localization
- `strings.py` → `strings_en.py` / `strings_ru.py` по `CONFIG["language"]`

## Other
- CI (ruff + pytest)
- CHANGELOG
- Export event → `.ics`
- Тест на `status_bar.update()` с mock
