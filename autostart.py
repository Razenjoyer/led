"""Автозапуск вместе с Windows: ярлык-скрипт в папке «Автозагрузка» текущего пользователя."""
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
STARTUP_FILE = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/LED Music.vbs"


def is_enabled():
    return STARTUP_FILE.exists()


def set_enabled(on):
    if not on:
        STARTUP_FILE.unlink(missing_ok=True)
        return
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{APP_DIR}"\r\n'
        f'sh.Run """{pythonw}"" ""{APP_DIR / "led_gui.py"}"" --tray", 0, False\r\n'
    )
    STARTUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    STARTUP_FILE.write_text(script, encoding="utf-16")  # utf-16 — чтобы пути с русскими буквами тоже работали
