# src/settings/rows.py
"""Готовые «строки» настроек: [label]  [control]  [helper]."""

from .widgets import make_label


class RowLayout:
    """Геометрия строки внутри контента вкладки.

    Отсчёт идёт сверху вниз, y уменьшается с каждой строкой.
    """

    def __init__(self, x, y_top, width):
        self.x = x
        self.y = y_top
        self.width = width
        self.label_w = 180
        self.gap = 12
        self.row_h = 26
        self.row_gap = 10
        self.helper_h = 20

    @property
    def control_x(self):
        return self.x + self.label_w + self.gap

    @property
    def control_w(self):
        return self.width - self.label_w - self.gap

    def next_y(self):
        y = self.y - self.row_h
        self.y = y - self.row_gap
        return y


def row_with_label(content, layout, text):
    """Добавляет label слева, возвращает (label, y) — контрол добавит вызывающий."""
    y = layout.next_y()
    lbl = make_label(text, (layout.x, y + 4, layout.label_w, 18))
    content.addSubview_(lbl)
    return lbl, y


def add_helper(content, layout, y, text, controls):
    """Мелкий серый текст под контролом. Не двигает layout.y."""
    h = make_label(text, (layout.control_x, y - 18, layout.control_w, 16), secondary=True, size=11)
    content.addSubview_(h)
    controls.append(h)
    return h


def add_helper_and_advance(content, layout, text, controls):
    """Хелпер под текущей строкой + сдвиг layout.y, чтобы следующая строка шла ниже."""
    y = layout.y + layout.row_gap
    h = make_label(text, (layout.control_x, y - 18, layout.control_w, 16), secondary=True, size=11)
    content.addSubview_(h)
    controls.append(h)
    layout.y -= layout.helper_h
    return h
