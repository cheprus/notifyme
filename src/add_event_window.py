# src/add_event_window.py — фрагмент parse_clipboard, остальное как было
from calendar_service import create_event_via_applescript, classify_url, _log

def parse_clipboard(text):
    result = {"title": "", "video_url": "", "url": "", "notes": ""}
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    title_match = re.search(r'Title:\s*(.+)', text, re.IGNORECASE)
    if title_match:
        title_text = title_match.group(1).strip()
    else:
        title_text = ""
        for line in lines:
            if not re.match(r'^(When|Location|Organizer|Description|Attendees):', line, re.IGNORECASE):
                if not re.match(r'^[A-Z][a-z]+, [A-Z][a-z]+ \d+, \d{4}', line):
                    title_text = line
                    break

    if title_text.startswith("http"):
        result["title"] = title_text
        result["url"] = title_text
    else:
        result["title"] = title_text

    # Все ссылки из текста
    all_links = re.findall(r'https?://[^\s<>"\']+', text)
    for link in all_links:
        kind = classify_url(link)
        if kind == 'meeting' and not result["video_url"]:
            result["video_url"] = link
        elif kind == 'tracker' and not result["url"]:
            result["url"] = link
        elif kind == 'unknown':
            # неизвестная ссылка: если url ещё пуст — в url, иначе в video_url
            if not result["url"]:
                result["url"] = link
            elif not result["video_url"]:
                result["video_url"] = link

    # Location: сначала явное поле, потом первая ссылка из video_url
    loc_match = re.search(r'Location:\s*(.+)', text, re.IGNORECASE)
    if loc_match:
        loc_text = loc_match.group(1).strip()
        if loc_text.startswith("http") and not result["video_url"]:
            result["video_url"] = loc_text

    desc_match = re.search(r'Description:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if desc_match:
        result["notes"] = desc_match.group(1).strip()

    return result
