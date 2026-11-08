"""Окно управления LED-лентой: цвет, режимы, палитры, будильник, таймер сна, трей и горячие клавиши.

Запуск: start.bat (или pythonw led_gui.py). С флагом --tray стартует свёрнутым в трей.
"""
import asyncio
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, ttk

import autostart
import engine
import palettes
from effects import MODE_INFO, MODE_LABELS, MODES, MUSIC_MODES, OTHER_MODES, PALETTE_MODES
from hotkeys import start_hotkeys
from protocol import ORDERS

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PRESETS = ["#ff0000", "#ff6000", "#ffd000", "#00ff00", "#00ffd0", "#0000ff", "#8000ff", "#ff00a0", "#ffffff"]
BG, FG, CARD, MUTED, ACCENT = "#1e1e24", "#f0f0f5", "#2a2a33", "#a0a0b0", "#ff2d8a"
HOTKEYS_HELP = ("Ctrl+Alt+L — вкл/выкл ленту\nCtrl+Alt+M — следующий режим\n"
                "Ctrl+Alt+P — следующая палитра\nCtrl+Alt+↑ / ↓ — ярче / темнее")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def make_button(parent, text, command, **kw):
    return tk.Button(parent, text=text, command=command, bg=CARD, fg=FG, activebackground="#3a3a46",
                     activeforeground=FG, relief="flat", padx=10, pady=4, cursor="hand2", **kw)


class App:
    def __init__(self, root, start_hidden=False):
        self.root = root
        self.state = engine.State(mode="manual", color=hex_to_rgb("#ff00a0"))
        self.state.load()
        self.actions = queue.Queue()  # действия из трея и горячих клавиш (другие потоки)
        self.tray = None
        self.setup_window()
        self.build_header()
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.build_light_tab(tabs)
        self.build_music_tab(tabs)
        self.build_time_tab(tabs)
        self.build_settings_tab(tabs)

        # Bluetooth, звук, экран и обложка работают в отдельном потоке, чтобы окно не подвисало
        threading.Thread(target=lambda: asyncio.run(engine.run(self.state)), daemon=True).start()
        self.start_tray()
        self.hotkey_errors = start_hotkeys([
            ("L", False, lambda: self.actions.put(self.toggle_power)),
            ("M", False, lambda: self.actions.put(lambda: self.cycle_mode(1))),
            ("P", False, lambda: self.actions.put(lambda: self.cycle_palette(1))),
            ("UP", True, lambda: self.actions.put(lambda: self.change_brightness(10))),
            ("DOWN", True, lambda: self.actions.put(lambda: self.change_brightness(-10))),
        ])
        if self.hotkey_errors:
            self.hotkeys_label.configure(text=HOTKEYS_HELP + "\n\nЗаняты другой программой: Ctrl+Alt+"
                                         + ", ".join(self.hotkey_errors))
        self.saved = self.state.to_dict()
        self.cover_seen = -1
        if start_hidden and self.tray:
            root.withdraw()
        self.refresh()

    # ---------- построение окна ----------

    def setup_window(self):
        root = self.root
        root.title("LED Music — ELK-BLEDDM C1")
        root.configure(bg=BG, padx=14, pady=12)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10), fieldbackground=CARD)
        style.configure("TRadiobutton", background=BG, foreground=FG)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TRadiobutton", background=[("active", BG)])
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Head.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=MUTED, padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])
        style.configure("TCombobox", foreground="#000000")

    def build_header(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x")
        self.power_btn = make_button(top, "Выключить", self.toggle_power, width=11)
        self.power_btn.pack(side="left")
        self.swatch = tk.Label(top, width=4, bg=rgb_to_hex(self.state.color))
        self.swatch.pack(side="right", ipady=5)
        self.status = ttk.Label(self.root, text="Запуск...", style="Muted.TLabel", wraplength=380)
        self.status.pack(anchor="w", pady=(6, 0))
        self.track = ttk.Label(self.root, text="", style="Muted.TLabel", wraplength=380)
        self.track.pack(anchor="w")

    def tab(self, tabs, title):
        frame = tk.Frame(tabs, bg=BG, padx=4, pady=8)
        tabs.add(frame, text=title)
        return frame

    def heading(self, parent, text, top=12):
        ttk.Label(parent, text=text, style="Head.TLabel").pack(anchor="w", pady=(top, 4))

    def build_light_tab(self, tabs):
        t = self.tab(tabs, "Свет")
        self.heading(t, "Цвет", top=0)
        grid = tk.Frame(t, bg=BG)
        grid.pack(anchor="w")
        for i, hx in enumerate(PRESETS):
            tk.Button(grid, bg=hx, activebackground=hx, width=3, relief="flat", cursor="hand2",
                      command=lambda c=hx: self.set_color(c)).grid(row=0, column=i, padx=2)
        make_button(t, "Выбрать любой цвет…", self.pick_color).pack(anchor="w", pady=(6, 0))

        self.heading(t, "Яркость")
        self.brightness = tk.Scale(t, from_=0, to=100, orient="horizontal", length=380, command=self.set_brightness,
                                   bg=BG, fg=FG, troughcolor=CARD, highlightthickness=0)
        self.brightness.set(int(self.state.brightness * 100))
        self.brightness.pack(anchor="w")

        self.heading(t, "Режим")
        self.mode = tk.StringVar(value=self.state.mode)
        cols = tk.Frame(t, bg=BG)
        cols.pack(anchor="w", fill="x")
        for c, (title, modes) in enumerate((("Под музыку", MUSIC_MODES), ("Свет и эффекты", OTHER_MODES))):
            col = tk.Frame(cols, bg=BG)
            col.grid(row=0, column=c, sticky="nw", padx=(0, 40))
            ttk.Label(col, text=title, style="Muted.TLabel").pack(anchor="w")
            for m in modes:
                ttk.Radiobutton(col, text=MODE_INFO[m][0], value=m, variable=self.mode,
                                command=lambda: self.set_mode(self.mode.get())).pack(anchor="w")
        self.mode_hint = ttk.Label(t, text="", style="Muted.TLabel")
        self.mode_hint.pack(anchor="w", pady=(4, 0))

        self.heading(t, "Палитра (басы → верха)")
        self.palette = tk.StringVar(value=self.state.palette)
        pal_frame = tk.Frame(t, bg=BG)
        pal_frame.pack(anchor="w")
        self.previews = {}
        for i, name in enumerate(palettes.PALETTES):
            row = tk.Frame(pal_frame, bg=BG)
            row.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 10), pady=2)
            ttk.Radiobutton(row, text=name, value=name, variable=self.palette, width=14,
                            command=lambda: self.set_palette(self.palette.get())).pack(side="left")
            canvas = tk.Canvas(row, width=64, height=14, highlightthickness=0, bg=BG, cursor="hand2")
            canvas.pack(side="left")
            canvas.bind("<Button-1>", lambda e, n=name: self.set_palette(n))
            self.previews[name] = canvas
            self.draw_preview(name)

    def build_music_tab(self, tabs):
        t = self.tab(tabs, "Музыка")
        self.music_info = ttk.Label(t, text="Темп: —", style="Head.TLabel")
        self.music_info.pack(anchor="w")

        self.heading(t, "Припев")
        self.chorus_on = tk.BooleanVar(value=self.state.chorus_switch)
        ttk.Checkbutton(t, text="Менять палитру на припеве (когда песня становится громче и плотнее)",
                        variable=self.chorus_on,
                        command=lambda: setattr(self.state, "chorus_switch", self.chorus_on.get())).pack(anchor="w")
        row = tk.Frame(t, bg=BG)
        row.pack(anchor="w", pady=(4, 0))
        ttk.Label(row, text="Палитра припева:").pack(side="left")
        auto = "Авто — та же, наоборот"
        names = [auto] + list(palettes.PALETTES)
        self.chorus_pal = ttk.Combobox(row, values=names, width=22, state="readonly")
        self.chorus_pal.set(auto if self.state.chorus_palette == "auto" else self.state.chorus_palette)
        self.chorus_pal.bind("<<ComboboxSelected>>", lambda e: setattr(
            self.state, "chorus_palette", "auto" if self.chorus_pal.get() == auto else self.chorus_pal.get()))
        self.chorus_pal.pack(side="left", padx=6)

        self.heading(t, "Реакция на удары")
        self.strobe = tk.BooleanVar(value=self.state.strobe)
        ttk.Checkbutton(t, text="Стробоскоп на дропах (быстрые вспышки — осторожно, если они вам неприятны)",
                        variable=self.strobe, command=self.set_strobe).pack(anchor="w")
        ttk.Label(t, text="Чувствительность к биту (1 — только сильные удары, 10 — даже слабые)",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.sens = tk.Scale(t, from_=1, to=10, orient="horizontal", length=380, command=self.set_sens,
                             bg=BG, fg=FG, troughcolor=CARD, highlightthickness=0)
        self.sens.set(round((2.0 - self.state.sens) / 0.1) + 1)
        self.sens.pack(anchor="w")

        self.heading(t, "Режим «Свой»")
        self.custom_vars = {}
        for key, label in (("speed", "Скорость реакции цвета"), ("flash", "Сила вспышек на бочке"),
                           ("base", "Яркость между ударами")):
            ttk.Label(t, text=label, style="Muted.TLabel").pack(anchor="w")
            sc = tk.Scale(t, from_=0, to=100, orient="horizontal", length=380, bg=BG, fg=FG, troughcolor=CARD,
                          highlightthickness=0, command=lambda v, k=key: self.set_custom(k, int(v)))
            sc.set(self.state.custom.get(key, 50))
            sc.pack(anchor="w")
        self.custom_sparkle = tk.BooleanVar(value=self.state.custom.get("sparkle", True))
        ttk.Checkbutton(t, text="Искры на хай-хэтах и тарелках", variable=self.custom_sparkle,
                        command=lambda: self.set_custom("sparkle", self.custom_sparkle.get())).pack(anchor="w")
        make_button(t, "Включить режим «Свой»", lambda: self.set_mode("custom")).pack(anchor="w", pady=(6, 0))

    def set_custom(self, key, value):
        self.state.custom = {**self.state.custom, key: value}

    def build_time_tab(self, tabs):
        t = self.tab(tabs, "Время")
        self.heading(t, "Будильник-рассвет", top=0)
        self.alarm_on = tk.BooleanVar(value=self.state.alarm_enabled)
        ttk.Checkbutton(t, text="Включить", variable=self.alarm_on, command=self.set_alarm).pack(anchor="w")
        row = tk.Frame(t, bg=BG)
        row.pack(anchor="w", pady=4)
        hh, mm = self.state.alarm_time.split(":")
        ttk.Label(row, text="Время:").pack(side="left")
        self.alarm_h = ttk.Spinbox(row, from_=0, to=23, width=3, format="%02.0f", command=self.set_alarm, wrap=True)
        self.alarm_m = ttk.Spinbox(row, from_=0, to=55, increment=5, width=3, format="%02.0f",
                                   command=self.set_alarm, wrap=True)
        self.alarm_h.set(hh)
        self.alarm_m.set(mm)
        self.alarm_h.pack(side="left", padx=(6, 0))
        ttk.Label(row, text=":").pack(side="left")
        self.alarm_m.pack(side="left")
        ttk.Label(row, text="   рассвет за").pack(side="left")
        self.alarm_len = ttk.Combobox(row, values=[10, 15, 20, 30, 45, 60], width=4, state="readonly")
        self.alarm_len.set(self.state.alarm_minutes)
        self.alarm_len.bind("<<ComboboxSelected>>", lambda e: self.set_alarm())
        self.alarm_len.pack(side="left", padx=4)
        ttk.Label(row, text="мин").pack(side="left")
        for w in (self.alarm_h, self.alarm_m):
            w.bind("<FocusOut>", lambda e: self.set_alarm())
            w.bind("<Return>", lambda e: self.set_alarm())
        ttk.Label(t, text="К этому времени лента плавно разгорится от тёмно-красного до тёплого белого и\n"
                          "продержится 30 минут (любое нажатие в окне её отпустит). Программа и компьютер\n"
                          "должны быть включены, компьютер не в спящем режиме.",
                  style="Muted.TLabel").pack(anchor="w")
        make_button(t, "Показать рассвет за 20 секунд", self.preview_sunrise).pack(anchor="w", pady=(6, 0))

        self.heading(t, "Таймер сна")
        row = tk.Frame(t, bg=BG)
        row.pack(anchor="w")
        for minutes in (15, 30, 60, 90):
            make_button(row, f"{minutes} мин", lambda m=minutes: self.start_sleep(m)).pack(side="left", padx=(0, 6))
        make_button(row, "Отменить", self.cancel_sleep).pack(side="left")
        self.sleep_label = ttk.Label(t, text="Лента плавно погаснет и выключится.", style="Muted.TLabel")
        self.sleep_label.pack(anchor="w", pady=(4, 0))

    def build_settings_tab(self, tabs):
        t = self.tab(tabs, "Настройки")
        row = tk.Frame(t, bg=BG)
        row.pack(anchor="w")
        ttk.Label(row, text="Порядок цветов ленты:", style="Head.TLabel").pack(side="left")
        self.order = tk.StringVar(value=self.state.order)
        box = ttk.Combobox(row, textvariable=self.order, values=ORDERS, width=6, state="readonly")
        box.pack(side="left", padx=8)
        box.bind("<<ComboboxSelected>>", lambda e: setattr(self.state, "order", self.order.get()))
        ttk.Label(t, text="Если красный горит зелёным, попробуйте другой порядок.", style="Muted.TLabel").pack(anchor="w")

        self.heading(t, "Запуск")
        self.autostart = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(t, text="Запускать вместе с Windows (сразу в трей)", variable=self.autostart,
                        command=lambda: autostart.set_enabled(self.autostart.get())).pack(anchor="w")
        self.to_tray = tk.BooleanVar(value=self.state.close_to_tray)
        ttk.Checkbutton(t, text="Крестик окна прячет программу в трей (возле часов)", variable=self.to_tray,
                        command=lambda: setattr(self.state, "close_to_tray", self.to_tray.get())).pack(anchor="w")
        make_button(t, "Выйти из программы", self.quit).pack(anchor="w", pady=(8, 0))

        self.heading(t, "Горячие клавиши (работают всегда)")
        self.hotkeys_label = ttk.Label(t, text=HOTKEYS_HELP, style="Muted.TLabel", justify="left")
        self.hotkeys_label.pack(anchor="w")

    def draw_preview(self, name):
        c = self.previews[name]
        c.delete("all")
        for x in range(64):
            rgb = palettes.palette_rgb(name, x / 63)
            c.create_line(x, 0, x, 14, fill=rgb_to_hex(v * 255 for v in rgb))

    # ---------- действия ----------

    def set_color(self, hx):
        self.state.touch()
        self.state.color = hex_to_rgb(hx)
        self.swatch.configure(bg=hx)
        self.set_mode("manual")
        if not self.state.power:
            self.toggle_power()

    def pick_color(self):
        _, hx = colorchooser.askcolor(color=rgb_to_hex(self.state.color), title="Цвет ленты")
        if hx:
            self.set_color(hx)

    def set_mode(self, mode):
        self.state.touch()
        self.state.mode = mode
        self.mode.set(mode)

    def cycle_mode(self, step):
        self.set_mode(MODES[(MODES.index(self.state.mode) + step) % len(MODES)])

    def set_palette(self, name):
        self.state.touch()
        self.state.palette = name
        self.palette.set(name)
        if self.state.mode not in PALETTE_MODES:
            self.set_mode("freq")  # палитра работает в музыкальных режимах

    def cycle_palette(self, step):
        names = list(palettes.PALETTES)
        self.set_palette(names[(names.index(self.state.palette) + step) % len(names)])

    def set_brightness(self, v):
        self.state.brightness = int(v) / 100

    def change_brightness(self, delta):
        self.state.touch()
        self.brightness.set(max(0, min(100, int(self.state.brightness * 100) + delta)))
        self.set_brightness(self.brightness.get())

    def set_strobe(self):
        self.state.strobe = self.strobe.get()

    def set_sens(self, v):
        # 1 — реагирует только на сильные удары, 10 — на самые слабые
        self.state.sens = round(2.0 - (int(v) - 1) * 0.1, 2)

    def toggle_power(self):
        self.state.touch()
        self.state.power = not self.state.power
        if self.state.power:
            self.state.cancel_sleep()

    def set_alarm(self):
        try:
            hh, mm = int(self.alarm_h.get()), int(self.alarm_m.get())
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except ValueError:
            hh, mm = map(int, self.state.alarm_time.split(":"))
        self.alarm_h.set(f"{hh:02d}")
        self.alarm_m.set(f"{mm:02d}")
        self.state.alarm_time = f"{hh:02d}:{mm:02d}"
        self.state.alarm_minutes = int(self.alarm_len.get())
        self.state.alarm_enabled = self.alarm_on.get()
        self.state.alarm_dismissed = ""

    def preview_sunrise(self):
        self.state.preview_start = time.monotonic()

    def start_sleep(self, minutes):
        self.state.touch()
        self.state.start_sleep(minutes)

    def cancel_sleep(self):
        self.state.cancel_sleep()

    # ---------- трей ----------

    def start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for i, col in enumerate([(255, 45, 138), (160, 60, 255), (0, 200, 255)]):
            draw.ellipse((6 + i * 6, 6 + i * 6, 58 - i * 6, 58 - i * 6), fill=col)
        put = self.actions.put
        menu = pystray.Menu(
            pystray.MenuItem("Открыть окно", lambda: put(self.show), default=True),
            pystray.MenuItem("Вкл / выкл ленту", lambda: put(self.toggle_power)),
            pystray.MenuItem("Следующий режим", lambda: put(lambda: self.cycle_mode(1))),
            pystray.MenuItem("Следующая палитра", lambda: put(lambda: self.cycle_palette(1))),
            pystray.MenuItem("Выход", lambda: put(self.quit)),
        )
        self.tray = pystray.Icon("led_music", img, "LED Music", menu)
        self.tray.run_detached()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self):
        if self.tray and self.state.close_to_tray:
            self.root.withdraw()
        else:
            self.quit()

    def quit(self):
        self.state.stop = True
        self.state.save()
        if self.tray:
            self.tray.stop()
        self.root.after(300, self.root.destroy)

    # ---------- обновление окна ----------

    def refresh(self):
        while not self.actions.empty():
            self.actions.get()()
        s = self.state
        self.status.configure(text=s.status)
        self.track.configure(text=f"Сейчас играет: {s.track}" if s.track else "")
        self.power_btn.configure(text="Выключить" if s.power else "Включить")
        if self.mode.get() != s.mode:
            self.mode.set(s.mode)
        self.mode_hint.configure(text=MODE_LABELS[s.mode])
        bpm = f"{s.bpm:.0f} BPM" if s.bpm >= 60 else "— (включите музыку)"
        self.music_info.configure(text=f"Темп: {bpm}" + ("   •   сейчас припев" if s.chorus_now else ""))
        if s.mode == "manual":
            self.swatch.configure(bg=rgb_to_hex(s.color))
        if s.cover_version != self.cover_seen:
            self.cover_seen = s.cover_version
            self.draw_preview(palettes.COVER_PALETTE)
        if s.sleep_end:
            left = max(0, int(s.sleep_end - time.time()))
            self.sleep_label.configure(text=f"Лента погаснет через {left // 60}:{left % 60:02d}")
        else:
            self.sleep_label.configure(text="Лента плавно погаснет и выключится.")
        if s.alarm_active:
            self.status.configure(text="Будильник: рассвет. Нажмите что-нибудь в окне, чтобы выключить.")
        current = s.to_dict()
        if current != self.saved:  # сохраняем настройки, когда что-то поменялось
            s.save()
            self.saved = current
        if self.tray:
            self.tray.title = f"LED Music — {MODE_LABELS[s.mode].split(' —')[0]}"
        self.root.after(300, self.refresh)


if __name__ == "__main__":
    root = tk.Tk()
    App(root, start_hidden="--tray" in sys.argv)
    root.mainloop()
