# ui.py
import objc
from datetime import datetime, timedelta
from AppKit import NSColor

def interpolate_color(color1, color2, t):
    r = color1[0] + (color2[0] - color1[0]) * t
    g = color1[1] + (color2[1] - color1[1]) * t
    b = color1[2] + (color2[2] - color1[2]) * t
    return (r, g, b)

def format_time_delta(minutes):
    """Преобразует минуты в человекочитаемый формат (например, '7 ч 16 мин')."""
    if minutes < 1:
        return "менее минуты"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        if mins > 0:
            return f"{hours} ч {mins} мин"
        return f"{hours} ч"
    return f"{mins} мин"

def get_gradient_color(delta_minutes, is_ongoing=False):
    """
    Возвращает NSColor на основе градиента важности.
    Цвета сделаны более яркими и насыщенными.
    """
    if is_ongoing:
        # --- ИДУЩИЕ ВСТРЕЧИ ---
        # 0-10 мин: ярко-красный -> оранжевый
        # 10-30 мин: оранжевый -> жёлтый
        # 30-60 мин: жёлтый -> сиреневый
        # >60 мин: сиреневый -> серо-фиолетовый (угасает)
        t = min(delta_minutes, 120.0)
        if t <= 10:
            local_t = t / 10.0
            rgb = interpolate_color((1.0, 0.0, 0.0), (1.0, 0.4, 0.0), local_t) # Ярче оранжевый
        elif t <= 30:
            local_t = (t - 10) / 20.0
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.8, 0.0), local_t) # Ярче жёлтый
        elif t <= 60:
            local_t = (t - 30) / 30.0
            rgb = interpolate_color((1.0, 0.8, 0.0), (0.7, 0.3, 1.0), local_t) # Ярче сиреневый
        else:
            local_t = min((t - 60) / 60.0, 1.0)
            rgb = interpolate_color((0.7, 0.3, 1.0), (0.5, 0.2, 0.7), local_t) # Угасающий фиолетовый
    else:
        # --- БУДУЩИЕ ВСТРЕЧИ ---
        # 0-5 мин: ярко-красный
        # 5-30 мин: оранжевый -> красно-розовый
        # 30-60 мин: красно-розовый -> жёлто-розовый
        # 60-120 мин: жёлто-розовый -> розово-сиреневый
        # >120 мин: розово-сиреневый -> синий
        t = min(delta_minutes, 180.0)
        if t <= 5:
            rgb = (1.0, 0.0, 0.0) # Чистый красный
        elif t <= 30:
            local_t = (t - 5) / 25.0
            rgb = interpolate_color((1.0, 0.4, 0.0), (1.0, 0.1, 0.3), local_t) # Оранжевый -> Ярко-малиновый
        elif t <= 60:
            local_t = (t - 30) / 30.0
            rgb = interpolate_color((1.0, 0.1, 0.3), (1.0, 0.5, 0.6), local_t) # Малиновый -> Розовый
        elif t <= 120:
            local_t = (t - 60) / 60.0
            rgb = interpolate_color((1.0, 0.5, 0.6), (0.6, 0.4, 1.0), local_t) # Розовый -> Ярко-сиреневый
        else:
            local_t = min((t - 120) / 60.0, 1.0)
            rgb = interpolate_color((0.6, 0.4, 1.0), (0.0, 0.4, 1.0), local_t) # Сиреневый -> Ярко-синий
    
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], 1.0)

def get_status_color(events):
    """
    Возвращает статус и цвет для трея.
    Приоритет: Красный (срочно) > Красно-розовый (5-30 мин) > Розовый (30-120 мин) 
    > Сиреневый (идет) > Синий (>2 часов) > Зеленый (нет встреч).
    """
    now = datetime.now()
    
    if not events:
        return "Нет встреч", (0.2, 0.8, 0.2) # Ярче зеленый

    next_future = None
    min_delta_future = float('inf')
    for ev in events:
        delta = (ev["start"] - now).total_seconds() / 60.0
        if delta > 0 and delta < min_delta_future:
            min_delta_future = delta
            next_future = ev

    ongoing_events = [ev for ev in events if ev["start"] <= now <= ev["end"]]

    # 1. Срочно (красный)
    if next_future and min_delta_future <= 5:
        return f"Через {format_time_delta(min_delta_future)}", (1.0, 0.0, 0.0)

    # 2. Идет сейчас (красный, если <= 10 мин)
    for ev in ongoing_events:
        minutes_ago = int((now - ev["start"]).total_seconds() // 60)
        if minutes_ago <= 10:
            return f"Идет {format_time_delta(minutes_ago)}", (1.0, 0.0, 0.0)

    # 3. Скоро (красно-розовый)
    if next_future and min_delta_future <= 30:
        return f"Через {format_time_delta(min_delta_future)}", (1.0, 0.1, 0.3)

    # 4. Не так скоро (розовый)
    if next_future and min_delta_future <= 120:
        return f"Через {format_time_delta(min_delta_future)}", (1.0, 0.5, 0.6)

    # 5. Идет давно (сиреневый)
    if ongoing_events:
        oldest = min(ongoing_events, key=lambda e: e["start"])
        minutes_ago = int((now - oldest["start"]).total_seconds() // 60)
        return f"Идет {format_time_delta(minutes_ago)}", (0.6, 0.4, 1.0)

    # 6. Далеко (синий)
    if next_future:
        return f"Через {format_time_delta(min_delta_future)}", (0.0, 0.4, 1.0)

    return "Нет встреч", (0.2, 0.8, 0.2)
