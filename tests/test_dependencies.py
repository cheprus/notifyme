# tests/test_dependencies.py
import importlib
import importlib.util
import sys

REQUIRED = {
    "rumps": "rumps",
    "pyobjc-framework-Cocoa": "objc",
    "pyobjc-framework-EventKit": "EventKit",
    "pyobjc-framework-ApplicationServices": "ApplicationServices",
    "pyobjc-framework-Quartz": "Quartz",
    "dateparser": "dateparser",
}


def test_all_dependencies_installed():
    missing = []
    for pip_name, module_name in REQUIRED.items():
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            missing.append(f"{pip_name} (import {module_name}): {e}")

    if missing:
        raise AssertionError(
            "Missing Python packages:\n  " + "\n  ".join(missing) +
            "\n\nRun:\n  /Library/Frameworks/Python.framework/Versions/3.13/bin/pip3 install -r requirements.txt"
        )


def test_pyinstaller_installed():
    if importlib.util.find_spec("PyInstaller") is None:
        raise AssertionError(
            "PyInstaller not installed.\n"
            "Run: /Library/Frameworks/Python.framework/Versions/3.13/bin/pip3 install pyinstaller"
        )


if __name__ == "__main__":
    tests = [test_all_dependencies_installed, test_pyinstaller_installed]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__}: {e}")
    if failed:
        sys.exit(1)
    print(f"All {len(tests)} tests passed")
