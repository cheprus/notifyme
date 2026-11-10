# src/settings/tabs/about.py
"""Вкладка About: имя, версия, дата, автор, лицензия, ссылка."""

import os
import plistlib

from AppKit import NSMakeRect, NSView, NSViewHeightSizable, NSViewWidthSizable

import version

from ..rows import RowLayout, row_with_label
from ..widgets import make_label


def _build_date():
    """Дата сборки из Info.plist (.app) или APP_DATE из version.py (dev)."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        info_plist = os.path.abspath(os.path.join(here, "..", "..", "..", "Info.plist"))
        if os.path.exists(info_plist):
            with open(info_plist, "rb") as f:
                info = plistlib.load(f)
            bd = info.get("BuildDate")
            if bd:
                return bd
    except Exception:
        pass
    return getattr(version, "APP_DATE", "")


class AboutTab:
    def __init__(self):
        self._callbacks = []
        self._view = None

    def view(self):
        if self._view is not None:
            return self._view

        w, h = 700, 480
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        v.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        layout = RowLayout(x=20, y_top=h - 20, width=w - 40)

        title = make_label(
            version.APP_NAME,
            NSMakeRect(layout.x, h - 60, layout.width, 32),
            bold=True, secondary=False, size=24,
        )
        v.addSubview_(title)

        version_lbl = make_label(
            f"Version {version.__version__}",
            NSMakeRect(layout.x, h - 88, layout.width, 20),
            secondary=True, size=13,
        )
        v.addSubview_(version_lbl)

        desc = make_label(
            version.APP_DESCRIPTION,
            NSMakeRect(layout.x, h - 130, layout.width, 40),
            secondary=False, size=13,
        )
        v.addSubview_(desc)

        layout.y = h - 180

        row_with_label(v, layout, "Author")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            version.APP_AUTHOR,
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=False, size=13,
        ))

        row_with_label(v, layout, "License")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            version.APP_LICENSE,
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=False, size=13,
        ))

        row_with_label(v, layout, "Version")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            version.__version__,
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=False, size=13,
        ))

        row_with_label(v, layout, "Released")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            version.APP_DATE,
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=False, size=13,
        ))

        row_with_label(v, layout, "Build")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            _build_date(),
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=False, size=13,
        ))

        row_with_label(v, layout, "Home")
        y = layout.y + layout.row_gap
        v.addSubview_(make_label(
            version.APP_URL,
            NSMakeRect(layout.control_x, y + 6, layout.control_w, 18),
            secondary=True, size=13,
        ))

        self._view = v
        return v
