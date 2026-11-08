"""Глобальные горячие клавиши Windows (работают, даже когда окно свёрнуто)."""
import ctypes
import threading
from ctypes import wintypes

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
WM_HOTKEY = 0x0312
VK = {"L": 0x4C, "M": 0x4D, "P": 0x50, "UP": 0x26, "DOWN": 0x28}


def start_hotkeys(bindings):
    """bindings: список (клавиша, повторять_при_удержании, функция) для Ctrl+Alt+клавиша.
    Функции вызываются в отдельном потоке. Возвращает список клавиш, которые заняты другой программой."""
    failed = []
    ready = threading.Event()

    def loop():
        user32 = ctypes.windll.user32
        for i, (key, repeat, _) in enumerate(bindings, 1):
            mods = MOD_CONTROL | MOD_ALT | (0 if repeat else MOD_NOREPEAT)
            if not user32.RegisterHotKey(None, i, mods, VK[key]):
                failed.append(key)
        ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and 1 <= msg.wParam <= len(bindings):
                try:
                    bindings[msg.wParam - 1][2]()
                except Exception as e:
                    print(f"[горячие клавиши] {e}")

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(2)
    return failed
