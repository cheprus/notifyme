# config.py
import os
import json

CONFIG_DIR = os.path.expanduser("~/.notifyme")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

def get_available_sounds():
    """Сканирует системную папку со звуками и возвращает словарь {Имя: Путь}."""
    sounds = {}
    sound_dir = "/System/Library/Sounds"
    if os.path.exists(sound_dir):
        for f in os.listdir(sound_dir):
            if f.endswith(".aiff"):
                name = f[:-5] # Убираем .aiff
                sounds[name] = os.path.join(sound_dir, f)
    return sounds

DEFAULT_CONFIG = {
    "notify_minutes_before": 5,
    "auto_close_minutes": 15,
    # По умолчанию берем Glass, если он есть, иначе первый попавшийся
    "sound_file": "/System/Library/Sounds/Glass.aiff" 
}

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config():
    ensure_config_dir()
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass
    
    # Если сохраненный звук больше не существует в системе, сбрасываем на дефолт
    available = get_available_sounds()
    if config["sound_file"] not in available.values():
        if "Glass" in available:
            config["sound_file"] = available["Glass"]
        elif available:
            config["sound_file"] = list(available.values())[0]
            
    return config

def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

CONFIG = load_config()
