# config.py
import os
import json

CONFIG_DIR = os.path.expanduser("~/.notifyme")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

DEFAULT_CONFIG = {
    "notify_minutes_before": 5,  # за сколько минут оповещать
    "auto_close_minutes": 15,    # через сколько минут закрывать окно
    "sound_file": "/System/Library/Sounds/Hero.aiff"
}

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config():
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Мержим с дефолтом на случай новых полей
                return {**DEFAULT_CONFIG, **config}
        except Exception:
            pass
    # Если файла нет или он битый — создаем дефолтный
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG

def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Загружаем один раз при старте
CONFIG = load_config()
