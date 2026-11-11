# src/telemost.py
"""Открывает Телемост в браузере. Пользователь создаёт звонок сам (+ → Новый звонок),
ссылка копируется Телемостом в буфер."""

import subprocess


def open_telemost() -> bool:
    try:
        subprocess.Popen(["open", "https://telemost.yandex.ru/"])
        return True
    except Exception as e:
        print(f"[TELEMOST] open failed: {e}", flush=True)
        return False
