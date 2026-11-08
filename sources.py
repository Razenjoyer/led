"""Источники цвета, кроме звука: обложка трека Spotify и экран компьютера."""
import asyncio
import colorsys
import io
import threading
import time

import numpy as np

import palettes


# ---------- Обложка трека ----------

def palette_from_image(data):
    """Главные цвета картинки → палитра (от тёмных к светлым). None, если картинка почти без цвета."""
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB").resize((48, 48))
    px = np.asarray(img, dtype=np.float32).reshape(-1, 3) / 255
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    colorful = px[(sat > 0.3) & (mx > 0.25)]
    if len(colorful) < 40:
        return None

    # k-means: ищем 5 основных цветов
    rng = np.random.default_rng(0)
    centers = colorful[rng.choice(len(colorful), 5, replace=False)]
    for _ in range(12):
        labels = np.argmin(((colorful[:, None, :] - centers[None]) ** 2).sum(-1), axis=1)
        centers = np.array([colorful[labels == k].mean(0) if np.any(labels == k) else centers[k] for k in range(5)])
    counts = np.bincount(labels, minlength=5)

    colors = []  # (оттенок, насыщенность, количество)
    for k in np.argsort(-counts):
        if counts[k] < len(colorful) * 0.04:
            continue
        h, s, _ = colorsys.rgb_to_hsv(*centers[k])
        if any(min(abs(h - h2), 1 - abs(h - h2)) < 0.04 for h2, _, _ in colors):
            continue  # почти такой же оттенок уже есть
        colors.append((h, s, counts[k]))
    if not colors:
        return None
    if len(colors) == 1:  # одноцветная обложка: добавим соседний оттенок, чтобы было движение
        h, s, n = colors[0]
        colors.append(((h + 0.07) % 1, s, n))

    # для ленты делаем цвета сочными и яркими; порядок — от тёмных (басы) к светлым (верха)
    rgbs = [colorsys.hsv_to_rgb(h, min(1.0, max(0.8, s * 1.3)), 1.0) for h, s, _ in colors[:5]]
    rgbs.sort(key=lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
    # между далёкими цветами (синий → оранжевый) прямой переход идёт через серый;
    # вставляем сочный цвет «по кругу оттенков», чтобы лента не тускнела на переходах
    result = [rgbs[0]]
    for a, b in zip(rgbs, rgbs[1:]):
        ha, hb = colorsys.rgb_to_hsv(*a)[0], colorsys.rgb_to_hsv(*b)[0]
        d = (hb - ha + 0.5) % 1 - 0.5  # кратчайший путь по кругу оттенков
        if abs(d) > 0.12:
            result.append(colorsys.hsv_to_rgb((ha + d / 2) % 1, 1.0, 1.0))
        result.append(b)
    return [tuple(round(float(v), 3) for v in c) for c in result]


async def watch_cover(state, interval=2.0):
    """Следит за тем, что играет (медиапанель Windows), и обновляет палитру «Обложка трека»."""
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        from winrt.windows.storage.streams import Buffer, InputStreamOptions
    except ImportError:
        return
    last_key = None
    while not state.stop:
        try:
            mgr = await Manager.request_async()
            sessions = list(mgr.get_sessions())
            session = next((s for s in sessions if "spotify" in s.source_app_user_model_id.lower()), None)
            session = session or mgr.get_current_session()
            if session:
                props = await session.try_get_media_properties_async()
                key = (props.artist, props.title)
                if key != last_key and props.thumbnail:
                    stream = await props.thumbnail.open_read_async()
                    buf = Buffer(stream.size)
                    await stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
                    colors = palette_from_image(bytes(memoryview(buf)))
                    palettes.PALETTES[palettes.COVER_PALETTE] = colors or list(palettes.PALETTES[palettes.DEFAULT_PALETTE])
                    state.track = f"{props.artist} — {props.title}" if props.artist else props.title
                    state.cover_version += 1
                    last_key = key
        except Exception as e:  # медиапанель может быть недоступна — просто пробуем позже
            print(f"[обложка] {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(interval)


# ---------- Экран ----------

def screen_color(frame_bgra):
    """Основной цвет кадра экрана, RGB 0..1. Яркие и насыщенные места весят больше, чем серые."""
    px = frame_bgra[::24, ::24, 2::-1].reshape(-1, 3).astype(np.float32) / 255  # BGRA → RGB, каждый 24-й пиксель
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    weight = sat**2 * mx + 0.02
    avg = (px * weight[:, None]).sum(0) / weight.sum()
    h, s, v = colorsys.rgb_to_hsv(*avg)
    bright = float(np.mean(mx))  # тёмная сцена — тусклая лента
    return colorsys.hsv_to_rgb(h, min(1.0, s * 1.5), max(0.04, min(1.0, bright * 1.3)))


def start_screen_sampler(state, fps=10):
    """Фоновый поток: пока выбран режим «Экран», снимает экран и пишет цвет в state.screen_rgb."""
    def loop():
        import mss
        grabber = getattr(mss, "MSS", None) or mss.mss
        with grabber() as sct:
            while not state.stop:
                if state.mode != "screen":
                    time.sleep(0.3)
                    continue
                try:
                    state.screen_rgb = screen_color(np.asarray(sct.grab(sct.monitors[1])))
                except Exception as e:
                    print(f"[экран] {e}")
                    time.sleep(1)
                time.sleep(1 / fps)

    threading.Thread(target=loop, daemon=True).start()
