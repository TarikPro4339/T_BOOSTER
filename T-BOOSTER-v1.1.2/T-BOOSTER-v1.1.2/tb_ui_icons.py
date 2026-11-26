"""DPI-independent line icons rendered as antialiased Tk-compatible PNGs."""

from functools import lru_cache
import math
import struct
import zlib


ICON_PATHS = {
    "about": (((5, 3), (19, 3), (19, 21), (5, 21), (5, 3)),
              ((12, 7), (12, 7)), ((12, 11), (12, 17)), ((10, 17), (14, 17))),
    "home": (((3, 11), (12, 3), (21, 11)), ((6, 9), (6, 21), (18, 21), (18, 9)),
             ((10, 21), (10, 15), (14, 15), (14, 21))),
    "tools": (((4, 8), (7, 8), (8, 5), (6, 3), (11, 3), (13, 6), (12, 10),
               (21, 18), (18, 21), (10, 12), (6, 13), (3, 11), (3, 7)),),
    "game": (((7, 7), (17, 7), (20, 9), (22, 17), (20, 20), (17, 19),
              (14, 16), (10, 16), (7, 19), (4, 20), (2, 17), (4, 9), (7, 7)),
             ((6, 12), (10, 12)), ((8, 10), (8, 14)), ((17, 11), (17, 11)), ((19, 14), (19, 14))),
    "roblox": (((7, 3), (21, 7), (17, 21), (3, 17), (7, 3)),
               ((11, 9), (15, 11), (13, 15), (9, 13), (11, 9))),
    "windows": (((3, 5), (21, 3), (21, 21), (3, 19), (3, 5)),
                ((11, 4), (11, 20)), ((3, 12), (21, 12))),
    "performance": (((3, 18), (3, 12), (6, 7), (12, 5), (18, 7), (21, 12), (21, 18), (3, 18)),
                    ((12, 14), (16, 9)), ((6, 13), (7, 13)), ((18, 13), (19, 13))),
    "vpn": (((12, 3), (20, 6), (20, 12), (18, 17), (12, 21), (6, 17), (4, 12), (4, 6), (12, 3)),
            ((9, 11), (15, 11), (15, 16), (9, 16), (9, 11)),
            ((10, 11), (10, 9), (12, 7), (14, 9), (14, 11))),
    "scan": (((3, 8), (3, 3), (8, 3)), ((16, 3), (21, 3), (21, 8)),
             ((3, 16), (3, 21), (8, 21)), ((16, 21), (21, 21), (21, 16)),
             ((6, 12), (18, 12))),
    "disk": (((5, 3), (19, 3), (21, 17), (21, 21), (3, 21), (3, 17), (5, 3)),
             ((3, 16), (21, 16)), ((7, 19), (7, 19)), ((12, 19), (12, 19))),
    "benchmark": (((4, 4), (4, 20), (21, 20)), ((7, 15), (11, 10), (15, 13), (21, 6)),
                  ((17, 6), (21, 6), (21, 10))),
    "tweaks": (((5, 3), (5, 9)), ((5, 13), (5, 21)), ((3, 11), (7, 11)),
               ((12, 3), (12, 14)), ((12, 18), (12, 21)), ((10, 16), (14, 16)),
               ((19, 3), (19, 6)), ((19, 10), (19, 21)), ((17, 8), (21, 8))),
    "memory": (((3, 6), (21, 6), (21, 17), (3, 17), (3, 6)),
               ((7, 10), (7, 13)), ((12, 10), (12, 13)), ((17, 10), (17, 13)),
               ((6, 17), (6, 20)), ((10, 17), (10, 20)), ((14, 17), (14, 20)), ((18, 17), (18, 20))),
    "restore": (((4, 10), (7, 5), (12, 3), (17, 4), (21, 8), (22, 13), (20, 18),
                (16, 21), (11, 21), (7, 19)), ((4, 5), (4, 10), (9, 10)),
               ((12, 8), (12, 13), (16, 15))),
    "logs": (((6, 3), (15, 3), (20, 8), (20, 21), (6, 21), (6, 3)),
             ((15, 3), (15, 8), (20, 8)), ((9, 12), (17, 12)), ((9, 16), (17, 16))),
    "bolt": (((13, 3), (5, 14), (11, 14), (10, 21), (19, 10), (13, 10), (13, 3)),),
    "rocket": (((8, 16), (6, 13), (10, 7), (15, 4), (21, 3), (20, 9), (17, 14), (11, 18), (8, 16)),
               ((6, 13), (3, 15), (3, 20), (8, 18)), ((11, 18), (9, 21), (14, 21), (16, 17)),
               ((16, 8), (16, 8))),
    "check": (((4, 12), (9, 17), (20, 6)),),
}


def encode_rgba_png(width, height, rows):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


@lru_cache(maxsize=96)
def render_line_icon(name, size, color):
    scale = size / 24
    stroke = 0.92 * scale
    alpha = bytearray(size * size)
    for path in ICON_PATHS[name]:
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            ax, ay, bx, by = x1 * scale, y1 * scale, x2 * scale, y2 * scale
            vx, vy = bx - ax, by - ay
            length_squared = vx * vx + vy * vy
            for y in range(max(0, int(min(ay, by) - stroke)),
                           min(size, math.ceil(max(ay, by) + stroke + 1))):
                for x in range(max(0, int(min(ax, bx) - stroke)),
                               min(size, math.ceil(max(ax, bx) + stroke + 1))):
                    dx, dy = x + 0.5 - ax, y + 0.5 - ay
                    along = (dx * vx + dy * vy) / length_squared if length_squared else 0
                    along = max(0, min(1, along))
                    distance = math.hypot(dx - along * vx, dy - along * vy)
                    coverage = round(255 * max(0, min(1, stroke + 0.5 - distance)))
                    offset = y * size + x
                    alpha[offset] = max(alpha[offset], coverage)
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for opacity in alpha[y * size:(y + 1) * size]:
            rows.extend((*color, opacity))
    return encode_rgba_png(size, size, rows)
