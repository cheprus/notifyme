# src/state_manager.py
import json
import os
from datetime import datetime

from config import STATE_FILE, ensure_dir


def load_state():
    """Возвращает (notified_ids_set, last_id_str_or_None)."""
    ensure_dir()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
                    return set(), None
                return set(data.get("ids", [])), data.get("last_id")
        except Exception:
            pass
    return set(), None


def save_state(notified_ids, last_id=None):
    """Сохраняет set ids + опционально last_id (последнее показанное)."""
    ensure_dir()
    try:
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ids": list(notified_ids),
            "last_id": last_id,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
