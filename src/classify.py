# src/classify.py
"""Классификация ссылок: tracker vs meeting."""

import re

from config import CONFIG

# ---------- Регулярки нормализации ----------

_ANY_ISSUE_URL_RE = re.compile(r"https?://[^\s]*?/issues/(\d+)", re.IGNORECASE)
_HASH_ISSUE_RE = re.compile(r"(?:^|\s)#(\d+)(?=\s|$|[,.;:!?])")
_URL_LIKE_RE = re.compile(r"^https?://", re.IGNORECASE)
_URL_STRICT_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


# ---------- Паттерны классификации ----------

_TRACKER_PATTERNS = [
    r"support\.igtel\.ru",
    r"tautoki",
    r"jira",
    r"confluence",
    r"atlassian\.net",
    r"github\.com",
    r"gitlab",
    r"bitbucket",
    r"youtrack",
    r"redmine",
    r"trello\.com",
    r"asana\.com",
    r"notion\.so",
    r"miro\.com",
    r"/issues/",
    r"/browse/",
    r"/tickets?/",
    r"/tasks?/",
    r"/wiki/",
]

_MEETING_PATTERNS = [
    r"\bmts-link\.ru",
    r"\bzoom\.us",
    r"\bmeet\.google\.com",
    r"\bteams\.microsoft\.com",
    r"\bwebex\.com",
    r"\bwhereby\.com",
    r"\bjitsi",
    r"\bmeet\.jivo\.ru",
    r"\bteam\.do\.orbitkom\.ru",
    r"\btelemost\.yandex\.ru",
    r"/j/\d+",
    r"/session/\d+",
    r"/meet/",
    r"/conference/",
]


# ---------- Вспомогательные ----------

def _custom_patterns(key):
    result = []
    for d in CONFIG.get(key, []) or []:
        d = (d or "").strip()
        if not d:
            continue
        result.append(re.escape(d))
    return result


def clean_url(s):
    if not s:
        return ""
    s = s.strip()
    return s.split(None, 1)[0] if s else ""


def looks_like_url(s):
    if not s:
        return False
    return bool(_URL_LIKE_RE.match(s.strip()))


def looks_like_clean_url(s):
    if not s:
        return False
    return bool(_URL_STRICT_RE.match(s.strip()))


# ---------- Публичные функции ----------

def normalize_title(title):
    if not title:
        return title
    t = title.strip()
    t = _ANY_ISSUE_URL_RE.sub(lambda m: f"#{m.group(1)}", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def recover_tracker_url(title, notes):
    haystack = " ".join(filter(None, [title or "", notes or ""]))

    for domain in CONFIG.get("custom_tracker_domains", []) or []:
        if not domain:
            continue
        m = re.search(r"https?://[^\s]*?" + re.escape(domain) + r"[^\s]*", haystack, re.IGNORECASE)
        if m:
            return clean_url(m.group(0))

    m = _ANY_ISSUE_URL_RE.search(haystack)
    if m:
        return clean_url(m.group(0))

    base = CONFIG.get("tracker_base_url", "").strip()
    if base:
        m = _HASH_ISSUE_RE.search(haystack)
        if m:
            if not base.endswith("/"):
                base += "/"
            return f"{base}{m.group(1)}"

    return ""


def classify_url(url):
    if not url:
        return "unknown"
    u = url.lower().strip()

    for pat in _custom_patterns("custom_meeting_domains"):
        if re.search(pat, u):
            return "meeting"

    for pat in _custom_patterns("custom_tracker_domains"):
        if re.search(pat, u):
            return "tracker"

    for pat in _MEETING_PATTERNS:
        if re.search(pat, u):
            return "meeting"
    for pat in _TRACKER_PATTERNS:
        if re.search(pat, u):
            return "tracker"
    return "unknown"


def split_links(tracker_url, meeting_url, notes):
    url_field = clean_url(tracker_url or "")
    location_field = clean_url(meeting_url or "")

    if url_field and location_field:
        url_kind = classify_url(url_field)
        loc_kind = classify_url(location_field)
        if url_kind == "meeting" and loc_kind == "tracker":
            return location_field, url_field
        return url_field, location_field

    if notes:
        found = re.findall(r'https?://[^\s<>"\']+', notes)
        for link in found:
            link = clean_url(link)
            kind = classify_url(link)
            if kind == "tracker" and not url_field:
                url_field = link
            elif kind == "meeting" and not location_field:
                location_field = link

    if url_field and not location_field:
        kind = classify_url(url_field)
        if kind == "meeting":
            location_field, url_field = url_field, ""
    if location_field and not url_field:
        kind = classify_url(location_field)
        if kind == "tracker":
            url_field, location_field = location_field, ""

    return url_field, location_field
