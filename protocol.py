"""Bluetooth-протокол лент ELK-BLEDOM / ELK-BLEDDM."""

WRITE_CHAR = "0000fff3-0000-1000-8000-00805f9b34fb"
POWER_ON = bytes.fromhex("7e0004f00001ff00ef")
POWER_OFF = bytes.fromhex("7e0004000000ff00ef")
DEFAULT_ADDRESS = "BE:68:38:01:5A:08"  # ELK-BLEDDM C1
DEFAULT_NAME = "ELK-BLEDDM C1"

ORDERS = ["RGB", "GRB", "BRG", "RBG", "GBR", "BGR"]
DEFAULT_ORDER = "GRB"  # у ленты ELK-BLEDDM C1 каналы идут в порядке G, R, B


def color_cmd(r, g, b, order="RGB"):
    """Команда цвета. order — порядок каналов в ленте: переставляем байты,
    чтобы на ленте загорелся именно тот цвет (r, g, b), который мы хотим."""
    rgb = {"R": r, "G": g, "B": b}
    c1, c2, c3 = (rgb[ch] for ch in order)
    return bytes([0x7E, 0x00, 0x05, 0x03, c1, c2, c3, 0x00, 0xEF])
