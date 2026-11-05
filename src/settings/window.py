# src/settings/window.py
"""NSPanel 720×560 + NSTabView. Один экземпляр на процесс."""

import objc
from AppKit import (
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSMakeRect,
    NSPanel,
    NSTabView,
    NSTabViewItem,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialSidebar,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSApplication, NSObject

from .binding import ConfigBinding
from .tabs.about import AboutTab
from .tabs.alarm import AlarmTab
from .tabs.calendar import CalendarTab
from .tabs.conferences import ConferencesTab
from .tabs.system import SystemTab

_WINDOW_W = 720
_WINDOW_H = 560
_TAB_PADDING = 6


class _Closer(NSObject):
    def initWithOuter_(self, outer):
        self = objc.super(_Closer, self).init()
        if self is None:
            return None
        self._outer = outer
        return self

    def windowWillClose_(self, note):
        outer = self._outer
        if outer is None:
            return
        try:
            outer._on_close()
        except Exception as e:
            print(f"[SETTINGS] on_close failed: {e}", flush=True)
        try:
            outer._binding.flush()
        except Exception as e:
            print(f"[SETTINGS] flush on close failed: {e}", flush=True)
        SettingsWindow._instance = None


class SettingsWindow(NSObject):
    _instance = None

    @classmethod
    def show(cls, store=None, on_change=None):
        if cls._instance is not None:
            cls._instance.run()
            return cls._instance
        cls._instance = cls.alloc().initWithStore_onChange_(store, on_change)
        cls._instance.run()
        return cls._instance

    def initWithStore_onChange_(self, store, on_change):
        self = objc.super(SettingsWindow, self).init()
        if self is None:
            return None
        self._store = store
        self._on_change = on_change
        self._callbacks = []
        self._binding = ConfigBinding(on_change=self._on_close_flush)
        self._panel = None
        self._tab_view = None
        self._tab_instances = {}
        return self

    def _on_close_flush(self):
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception as e:
                print(f"[SETTINGS] on_change failed: {e}", flush=True)

    def _on_close(self):
        for name, tab in self._tab_instances.items():
            cleanup = getattr(tab, "cleanup", None)
            if cleanup is None:
                continue
            try:
                cleanup()
            except Exception as e:
                print(f"[SETTINGS] cleanup {name} failed: {e}", flush=True)

    def _make_tab_item(self, identifier, label, view):
        item = NSTabViewItem.alloc().initWithIdentifier_(identifier)
        item.setLabel_(label)
        item.setView_(view)
        return item

    def _build_tabs(self):
        self._tab_instances = {}

        alarm_tab = AlarmTab(self._binding)
        self._tab_instances["alarm"] = alarm_tab
        item_alarm = self._make_tab_item("alarm", "Alarm", alarm_tab.view())

        conf_tab = ConferencesTab(self._binding)
        self._tab_instances["conferences"] = conf_tab
        item_conf = self._make_tab_item("conferences", "Conferences", conf_tab.view())

        cal_tab = CalendarTab(self._binding, store=self._store)
        self._tab_instances["calendar"] = cal_tab
        item_cal = self._make_tab_item("calendar", "Calendar", cal_tab.view())

        sys_tab = SystemTab(self._binding, reload_callback=self.reload_tabs)
        self._tab_instances["system"] = sys_tab
        item_sys = self._make_tab_item("system", "System", sys_tab.view())

        about_tab = AboutTab()
        self._tab_instances["about"] = about_tab
        item_about = self._make_tab_item("about", "About", about_tab.view())

        return [item_alarm, item_conf, item_cal, item_sys, item_about]

    def reload_tabs(self):
        if self._tab_view is None:
            return
        current_idx = self._tab_view.indexOfTabViewItem_(self._tab_view.selectedTabViewItem())
        try:
            for item in list(self._tab_view.tabViewItems()):
                self._tab_view.removeTabViewItem_(item)
            for item in self._build_tabs():
                self._tab_view.addTabViewItem_(item)
            items = self._tab_view.tabViewItems()
            if items and 0 <= current_idx < len(items):
                self._tab_view.selectTabViewItem_(items[current_idx])
            print("[SETTINGS] tabs reloaded", flush=True)
        except Exception as e:
            print(f"[SETTINGS] reload_tabs failed: {e}", flush=True)

    def _build_panel(self):
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, _WINDOW_W, _WINDOW_H),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("NotifyMe — Settings")
        panel.setReleasedWhenClosed_(False)
        panel.setFloatingPanel_(False)
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setHidesOnDeactivate_(False)
        panel.center()

        effect = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, _WINDOW_W, _WINDOW_H))
        effect.setMaterial_(NSVisualEffectMaterialSidebar)
        effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        effect.setState_(NSVisualEffectStateActive)
        effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

        tab_view = NSTabView.alloc().initWithFrame_(NSMakeRect(
            _TAB_PADDING, _TAB_PADDING,
            _WINDOW_W - 2 * _TAB_PADDING,
            _WINDOW_H - 2 * _TAB_PADDING - 16,
        ))
        tab_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self._tab_view = tab_view

        for item in self._build_tabs():
            tab_view.addTabViewItem_(item)

        effect.addSubview_(tab_view)
        panel.setContentView_(effect)

        closer = _Closer.alloc().initWithOuter_(self)
        panel.setDelegate_(closer)
        self._callbacks.append(closer)

        self._panel = panel
        return panel

    def _activate_app(self):
        app = NSApplication.sharedApplication()
        try:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception:
            pass
        try:
            app.activateIgnoringOtherApps_(True)
        except Exception:
            pass

    def run(self):
        if self._panel is not None:
            try:
                self._panel.makeKeyAndOrderFront_(None)
                self._panel.orderFrontRegardless()
            except Exception:
                pass
            self._activate_app()
            return self._panel
        panel = self._build_panel()
        self._activate_app()
        panel.makeKeyAndOrderFront_(None)
        panel.orderFrontRegardless()
        return panel
