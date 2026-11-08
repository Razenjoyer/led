"""Светомузыка для LED-ленты ELK-BLEDOM / ELK-BLEDDM — версия для консоли (без окна).

Запуск:  python led_music.py --mode freq --palette Огонь
         python led_music.py --mode manual --color ff0000
Остановка: Ctrl+C. Окно управления: led_gui.py (start.bat).
"""
import argparse
import asyncio
import time  # noqa: F401 — тесты подменяют time.monotonic через этот модуль

from audio import BLOCK, Analyzer, start_audio  # noqa: F401
from effects import MODES, Effects  # noqa: F401
from engine import State, compute_output, run  # noqa: F401
from palettes import COVER_PALETTE, DEFAULT_PALETTE, PALETTES, hsv, palette_rgb, pingpong, shade  # noqa: F401
from protocol import (DEFAULT_ADDRESS, DEFAULT_ORDER, ORDERS, POWER_OFF, POWER_ON,  # noqa: F401
                      WRITE_CHAR, color_cmd)


def main():
    ap = argparse.ArgumentParser(description="Светомузыка для ленты ELK-BLEDOM")
    ap.add_argument("--mode", choices=MODES, default="freq", help="режим (как в окне)")
    ap.add_argument("--color", default="ff0078", help="цвет для режима manual, например ff0000")
    ap.add_argument("--brightness", type=int, default=100, help="яркость 0–100")
    ap.add_argument("--palette", default=DEFAULT_PALETTE, choices=list(PALETTES), help="палитра")
    ap.add_argument("--order", default=DEFAULT_ORDER, choices=ORDERS,
                    help="порядок цветов в ленте (если красный горит зелёным — поменяйте)")
    ap.add_argument("--strobe", action="store_true", help="стробоскоп на дропах")
    ap.add_argument("--address", default=DEFAULT_ADDRESS, help="MAC-адрес ленты")
    ap.add_argument("--sens", type=float, default=1.4, help="порог бита: меньше — чувствительнее (1.2–1.8)")
    ap.add_argument("--fps", type=int, default=25, help="сколько раз в секунду обновлять цвет")
    args = ap.parse_args()
    state = State(args.mode, tuple(bytes.fromhex(args.color.lstrip("#"))), args.brightness / 100, args.sens)
    state.palette, state.order, state.strobe = args.palette, args.order, args.strobe
    try:
        asyncio.run(run(state, args.address, args.fps))
    except KeyboardInterrupt:
        print("Выход.")


if __name__ == "__main__":
    main()
