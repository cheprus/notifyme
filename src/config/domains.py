# src/config/domains.py
"""Дефолтные домены-подсказки для пользователя (не для classify).

Реальные паттерны классификации живут в src/classify.py.
Здесь — только стартовые значения, которые UI подставляет
в Settings → Conferences при первом запуске и по кнопке Reset to known.
"""

KNOWN_TRACKER_DOMAINS = [
    "support.igtel.ru",
    "tautoki",
    "jira",
    "confluence",
    "github.com",
    "gitlab.com",
    "youtrack",
    "redmine",
]

KNOWN_MEETING_DOMAINS = [
    "mts-link.ru",
    "zoom.us",
    "meet.google.com",
    "teams.microsoft.com",
    "webex.com",
    "whereby.com",
    "meet.jivo.ru",
]
