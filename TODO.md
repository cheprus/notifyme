# TODO

## AI (DeepSeek)
- Settings → вкладка AI: api_key, model, system prompt, reminders
- `src/ai.py` + `tests/test_ai.py`
- Меню → Ask AI…

## CLI
- `notifyme --settings` / `--about` / `--version`

## Audio
- CoreAudio listener → автообновление списка Output
- Alarm-pulse без переключения системного default на каждый цикл

## Localization
- `strings.py` → `strings_en.py` / `strings_ru.py` по `CONFIG["language"]`

## Other
- CI (ruff + pytest)
- CHANGELOG
- Export event → `.ics`
- Тест на `status_bar.update()` с mock
