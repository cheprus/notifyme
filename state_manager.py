# state_manager.py
import os
import json
from datetime import datetime, timedelta
from config import STATE_FILE, ensure_config_dir

def load_state():
    ensure_config_dir()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
                    return set()
                return set(data.get("ids", []))
        except Exception:
            pass
    return set()

def save_state(notified_ids):
    ensure_config_dir()
    try:
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ids": list(notified_ids)
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
