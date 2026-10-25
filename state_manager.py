# state_manager.py
import os
import json
from datetime import datetime

STATE_FILE = os.path.expanduser("~/.notifyme_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                # Проверяем, не устарело ли состояние (сменился день)
                if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
                    return set() # Сброс
                return set(data.get("ids", []))
        except Exception:
            pass
    return set()

def save_state(notified_ids):
    try:
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ids": list(notified_ids)
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
