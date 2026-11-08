"""Палитры и работа с цветом."""
import colorsys

# Цвета от «басов» (начало) к «верхам» (конец), RGB 0..1.
PALETTES = {
    "Тепло и холод": [(1, 0, 0), (1, 0, 0.5), (0.6, 0, 1), (0, 0.25, 1), (0, 0.9, 1)],
    "Огонь": [(0.8, 0, 0), (1, 0.1, 0), (1, 0.35, 0), (1, 0.6, 0), (1, 0.85, 0)],
    "Океан": [(0, 0, 0.9), (0, 0.3, 1), (0, 0.75, 1), (0, 1, 0.6), (0.45, 1, 0.85)],
    "Закат": [(0.45, 0, 0.9), (0.9, 0, 0.7), (1, 0, 0.25), (1, 0.35, 0), (1, 0.75, 0)],
    "Неон": [(1, 0, 0.6), (0.7, 0, 1), (0, 0.4, 1), (0, 1, 1), (0.4, 1, 0)],
    "Лес": [(0.6, 0.25, 0), (0.75, 0.6, 0), (0.25, 1, 0), (0, 0.8, 0.25), (0, 1, 0.65)],
    "Радуга": [(1, 0, 0), (1, 0.6, 0), (0.9, 1, 0), (0, 1, 0), (0, 1, 1), (0, 0.2, 1), (0.6, 0, 1)],
}
DEFAULT_PALETTE = "Тепло и холод"
# Палитра из обложки текущего трека Spotify; цвета подставляются на лету (см. sources.py)
COVER_PALETTE = "Обложка трека"
PALETTES[COVER_PALETTE] = list(PALETTES[DEFAULT_PALETTE])


def palette_rgb(name, t):
    """Цвет палитры в точке t (0..1), RGB 0..1."""
    stops = PALETTES.get(name) or PALETTES[DEFAULT_PALETTE]
    if len(stops) == 1:
        return tuple(stops[0])
    t = max(0.0, min(1.0, t)) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    return tuple(a + (b - a) * f for a, b in zip(stops[i], stops[i + 1]))


def shade(rgb, value=1.0, spark=0.0, spark_rgb=(1, 1, 1)):
    """Подмешивает цвет искры и задаёт яркость; возвращает RGB 0..255."""
    value = max(0.0, min(1.0, value))
    return tuple(int(255 * value * (c + (s - c) * spark)) for c, s in zip(rgb, spark_rgb))


def pingpong(x):
    """0→1→0 по кругу, чтобы плавное переливание не прыгало с конца палитры на начало."""
    x %= 1.0
    return 1 - abs(2 * x - 1)


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def mix(a, b, t):
    """Смешивает два цвета RGB 0..255."""
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))
