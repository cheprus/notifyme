# src/config/paths.py
import os

CONFIG_DIR = os.environ.get("NOTIFYME_CONFIG_DIR") or os.path.expanduser("~/.notifyme")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")


def ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)
