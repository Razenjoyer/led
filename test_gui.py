"""Автопроверка окна: открывает его, переключает всё подряд, делает снимки вкладок и закрывает.
Настройки пользователя (settings.json) сохраняются и восстанавливаются после теста."""
import shutil
import sys
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

import engine
import led_gui

settings = engine.SETTINGS_FILE
backup = settings.with_suffix(".bak")
if settings.exists():
    shutil.copy(settings, backup)

shots = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
root = tk.Tk()
app = led_gui.App(root)
tabs = root.nametowidget(root.winfo_children()[3])  # Notebook
log = []


def snap(name):
    root.attributes("-topmost", True)  # окно поверх других, чтобы на снимок не попало чужое
    root.lift()
    root.update()
    root.after(150)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height())).save(shots / f"gui_{name}.png")
    root.attributes("-topmost", False)


def check(label, cond):
    log.append(f"{'ок ' if cond else 'ОШИБКА'} {label}")


steps = [
    (5000, lambda: log.append("статус: " + app.state.status)),
    (5200, lambda: snap("1_light")),
    (5300, lambda: tabs.select(1)),
    (5500, lambda: snap("2_music")),
    (5600, lambda: tabs.select(2)),
    (5800, lambda: snap("3_time")),
    (5850, lambda: tabs.select(3)),
    (5950, lambda: (snap("4_settings"), tabs.select(0))),
    (6000, lambda: app.set_color("#ff0000")),
    (6800, lambda: app.set_color("#00ff00")),
    (7600, lambda: app.set_color("#0000ff")),
    (8000, lambda: check("ручной цвет синий", app.state.color == (0, 0, 255) and app.state.mode == "manual")),
    (8400, lambda: app.set_palette("Огонь")),
    (8500, lambda: check("палитра «Огонь» включает режим «Частоты»", app.state.mode == "freq")),
    (9000, lambda: app.set_mode("calm")),
    (9500, lambda: app.cycle_mode(1)),
    (9600, lambda: check("следующий режим после «Плавного» — «Свой»", app.state.mode == "custom")),
    (9650, lambda: app.set_custom("flash", 10)),
    (9700, lambda: check("ползунок «Своего» сохраняется", app.state.custom["flash"] == 10)),
    (9750, lambda: (app.set_mode("candle"), check("эффект «Свеча»", app.state.mode == "candle"))),
    (9760, lambda: app.set_mode("tempo")),
    (9800, lambda: app.cycle_palette(1)),
    (9900, lambda: check("следующая палитра после «Огня» — «Океан»", app.state.palette == "Океан")),
    (10000, lambda: app.change_brightness(-30)),
    (10100, lambda: check("яркость 70%", abs(app.state.brightness - 0.7) < 1e-6)),
    (10200, lambda: app.start_sleep(15)),
    (10600, lambda: check("таймер сна идёт: " + app.sleep_label.cget("text"), app.state.sleep_end is not None)),
    (10700, app.cancel_sleep),
    (10800, lambda: (app.alarm_on.set(True), app.alarm_h.set("6"), app.alarm_m.set("45"), app.set_alarm())),
    (10900, lambda: check("будильник 06:45", app.state.alarm_enabled and app.state.alarm_time == "06:45")),
    (11000, lambda: (app.alarm_on.set(False), app.set_alarm())),
    (11100, lambda: check("горячие клавиши зарегистрированы", not app.hotkey_errors)),
    (11200, lambda: check("иконка в трее есть", app.tray is not None)),
    (11300, lambda: app.toggle_power()),
    (12300, lambda: app.toggle_power()),
    (12400, lambda: app.set_mode("screen")),
    (14500, lambda: log.append(f"цвет экрана сейчас: {tuple(round(v, 2) for v in app.state.screen_rgb)}")),
    (14600, lambda: (app.set_palette("Тепло и холод"), app.set_brightness(100))),
    (15000, lambda: log.append("статус в конце: " + app.state.status)),
    (15100, app.quit),
]
for ms, fn in steps:
    root.after(ms, fn)
root.mainloop()

if backup.exists():
    shutil.move(backup, settings)
else:
    settings.unlink(missing_ok=True)
print("\n".join(log))
