# setup.py
from setuptools import setup

APP = ['app.py']
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': False,  # временно False, чтобы приложение запускалось из Applications
        'CFBundleName': 'NotifyMe',
        'CFBundleDisplayName': 'NotifyMe',
        'CFBundleIdentifier': 'com.chep.notifyme',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSCalendarsFullAccessUsageDescription': 'NotifyMe показывает ваши встречи и напоминает о них.',
    },
    'packages': [
        'rumps',
        'objc',
        'AppKit',
        'Foundation',
        'EventKit',
        'calendar_service',
        'state_manager',
        'ui',
        'calendar_icon',
    ],
}

setup(
    app=APP,
    name="NotifyMe",
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
