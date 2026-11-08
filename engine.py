"""Сердце программы: настройки, будильник-рассвет, таймер сна и связь с лентой."""
import asyncio
import datetime as dt
import json
import time
from pathlib import Path

from bleak import BleakClient

from audio import start_audio_in_thread
from effects import Effects
from palettes import DEFAULT_PALETTE
from protocol import DEFAULT_ADDRESS, DEFAULT_ORDER, POWER_OFF, POWER_ON, WRITE_CHAR, color_cmd
from sources import start_screen_sampler, watch_cover

SETTINGS_FILE = Path(__file__).with_name("settings.json")
SAVED_KEYS = ["mode", "color", "brightness", "sens", "palette", "order", "strobe",
              "alarm_enabled", "alarm_time", "alarm_minutes", "close_to_tray"]
ALARM_HOLD_MINUTES = 30  # сколько держать тёплый свет после времени будильника
PREVIEW_SECONDS = 20


class State:
    """Настройки, которые можно менять на лету (из окна, трея, горячих клавиш)."""

    def __init__(self, mode="beat", color=(255, 0, 120), brightness=1.0, sens=1.4):
        self.mode = mode
        self.color = tuple(color)  # цвет для ручного режима
        self.brightness = brightness  # 0..1, действует во всех режимах
        self.sens = sens
        self.palette = DEFAULT_PALETTE
        self.order = DEFAULT_ORDER  # порядок каналов в ленте
        self.strobe = False  # стробоскоп на дропах
        self.close_to_tray = True  # крестик окна прячет программу в трей
        self.power = True
        # будильник-рассвет
        self.alarm_enabled = False
        self.alarm_time = "07:30"
        self.alarm_minutes = 30
        self.alarm_dismissed = ""  # дата будильника, который уже выключили руками
        self.alarm_active = None  # дата будильника, который светит прямо сейчас
        self.preview_start = None  # time.monotonic() начала показа рассвета
        # таймер сна
        self.sleep_end = None  # time.time(), когда лента погаснет
        self.sleep_total = 0.0
        # служебное
        self.status = "Запуск..."
        self.track = ""
        self.cover_version = 0
        self.screen_rgb = (0.0, 0.0, 0.0)
        self.stop = False

    def set_status(self, text):
        self.status = text
        print(text)

    def touch(self):
        """Пользователь что-то нажал: если сейчас светит будильник — выключаем его на сегодня."""
        if self.alarm_active:
            self.alarm_dismissed = self.alarm_active
        self.preview_start = None

    def start_sleep(self, minutes):
        self.sleep_total = minutes * 60
        self.sleep_end = time.time() + self.sleep_total
        self.power = True

    def cancel_sleep(self):
        self.sleep_end = None

    # --- сохранение настроек между запусками ---
    def to_dict(self):
        return {k: getattr(self, k) for k in SAVED_KEYS}

    def load(self, path=SETTINGS_FILE):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for k in SAVED_KEYS:
            if k in data:
                setattr(self, k, tuple(data[k]) if k == "color" else data[k])

    def save(self, path=SETTINGS_FILE):
        try:
            Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            print(f"[настройки] не удалось сохранить: {e}")


# ---------- Будильник-рассвет ----------

SUNRISE = [  # (доля пути, цвет, яркость): от тёмно-красного к тёплому белому
    (0.0, (255, 0, 0), 0.01),
    (0.35, (255, 40, 0), 0.15),
    (0.7, (255, 110, 20), 0.5),
    (1.0, (255, 170, 70), 1.0),
]


def sunrise_color(p):
    p = max(0.0, min(1.0, p))
    for (p0, c0, v0), (p1, c1, v1) in zip(SUNRISE, SUNRISE[1:]):
        if p <= p1:
            f = (p - p0) / (p1 - p0)
            v = v0 + (v1 - v0) * f
            return tuple(int((a + (b - a) * f) * v) for a, b in zip(c0, c1))
    return SUNRISE[-1][1]


def alarm_phase(state, now):
    """Доля рассвета 0..1, если сейчас идёт рассвет (или держится свет после него), иначе None."""
    state.alarm_active = None
    if not state.alarm_enabled:
        return None
    try:
        hh, mm = (int(x) for x in state.alarm_time.split(":"))
        alarm_t = dt.time(hh, mm)
    except ValueError:
        return None
    for day in (now.date(), now.date() + dt.timedelta(days=1)):
        alarm = dt.datetime.combine(day, alarm_t)
        start = alarm - dt.timedelta(minutes=state.alarm_minutes)
        end = alarm + dt.timedelta(minutes=ALARM_HOLD_MINUTES)
        if start <= now < end and state.alarm_dismissed != day.isoformat():
            state.alarm_active = day.isoformat()
            total = max(1.0, (alarm - start).total_seconds())
            return min(1.0, (now - start).total_seconds() / total)
    return None


def sleep_factor(state, now=None):
    """Множитель яркости для таймера сна: 1 → 0. Когда время вышло — выключает ленту."""
    if state.sleep_end is None:
        return 1.0
    left = state.sleep_end - (now or time.time())
    if left <= 0:
        state.sleep_end = None
        state.power = False
        return 0.0
    return min(1.0, left / max(1.0, state.sleep_total))


def compute_output(state, effects, snapshot, dt_s, now=None):
    """Итог одного кадра: (включена ли лента, цвет RGB 0..255)."""
    if state.preview_start is not None:  # кнопка «Показать рассвет»: весь рассвет за 20 секунд
        elapsed = time.monotonic() - state.preview_start
        if elapsed < PREVIEW_SECONDS:
            return True, sunrise_color(elapsed / PREVIEW_SECONDS)
        state.preview_start = None
    phase = alarm_phase(state, now or dt.datetime.now())
    if phase is not None:
        return True, sunrise_color(phase)
    if not state.power:
        return False, (0, 0, 0)
    r, g, b = effects.frame(*snapshot, dt_s)
    k = max(0.0, min(1.0, state.brightness)) * sleep_factor(state)
    if not state.power:  # таймер сна только что закончился
        return False, (0, 0, 0)
    return True, (int(r * k), int(g * k), int(b * k))


# ---------- Связь с лентой ----------

async def run(state, address=DEFAULT_ADDRESS, fps=25):
    analyzer, stream, p = start_audio_in_thread(state.sens)
    effects = Effects(state)
    start_screen_sampler(state)
    cover_task = asyncio.create_task(watch_cover(state))
    period = 1 / fps
    try:
        while not state.stop:
            try:
                state.set_status(f"Подключаюсь к ленте {address}...")
                async with BleakClient(address, timeout=20) as client:
                    state.set_status("Лента подключена")
                    sent_power, sent_color, last_t = None, None, time.monotonic()
                    while client.is_connected and not state.stop:
                        now = time.monotonic()
                        analyzer.sens = state.sens
                        power, rgb = compute_output(state, effects, analyzer.snapshot(), now - last_t)
                        last_t = now
                        if power != sent_power:
                            await client.write_gatt_char(WRITE_CHAR, POWER_ON if power else POWER_OFF, response=False)
                            sent_power, sent_color = power, None
                        if power and (rgb, state.order) != sent_color:
                            await client.write_gatt_char(WRITE_CHAR, color_cmd(*rgb, state.order), response=False)
                            sent_color = (rgb, state.order)
                        await asyncio.sleep(period)
            except Exception as e:  # обрыв связи или лента занята телефоном — пробуем снова
                state.set_status(f"Нет связи с лентой ({e}). Пробую снова...")
                await asyncio.sleep(3)
    finally:
        cover_task.cancel()
        stream.stop_stream()
        stream.close()
        p.terminate()
