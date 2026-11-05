#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icons.py —— 生成 PWA / Apple Touch 图标（纯 Python，无第三方依赖）

深蓝圆角底 + 白色 "V" 字（两条圆头粗线段），2x 超采样抗锯齿。
输出到 icons/：icon-192.png、icon-512.png、icon-180.png（apple）、icon-maskable-512.png。

用法：python3 tools/make_icons.py
"""

import math
import os
import struct
import zlib

NAVY = (58, 87, 149)        # #3a5795，与应用主题一致
NAVY_DARK = (49, 81, 139)   # 底部微渐变
WHITE = (255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def write_png(path, w, h, rows_rgba):
    """rows_rgba: list of bytearray rows (w*4 bytes)。写入 32 位 RGBA PNG。"""

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(r) for r in rows_rgba)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def seg_dist(px, py, x1, y1, x2, y2):
    """点到线段的距离。"""
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def make_icon(size, maskable=False):
    """生成 size×size 的图标。maskable=True 时为满幅方形（安全区内缩内容）。"""
    ss = 2                       # 超采样倍率
    S = size * ss
    radius = 0 if maskable else int(S * 0.20)
    stroke = S * (0.085 if maskable else 0.095)
    # "V" 三个顶点（比例坐标）
    if maskable:  # 内容缩进到安全区（约 78%）
        ax, ay = (0.36, 0.34)
        bx, by = (0.50, 0.645)
        cx, cy = (0.64, 0.34)
    else:
        ax, ay = (0.31, 0.30)
        bx, by = (0.50, 0.70)
        cx, cy = (0.69, 0.30)

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            # 2x2 超采样
            acc = [0, 0, 0, 0]
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    px, py = (x + sx) * ss, (y + sy) * ss
                    # 圆角方形容差
                    if radius:
                        cxr = min(max(px, radius), S - radius)
                        cyr = min(max(py, radius), S - radius)
                        if math.hypot(px - cxr, py - cyr) > radius:
                            acc[3] += 64
                            continue
                    # 渐变底
                    t = py / S
                    base = tuple(int(NAVY[i] + (NAVY_DARK[i] - NAVY[i]) * t) for i in range(3))
                    # V 字：两条圆头线段
                    d = min(seg_dist(px, py, ax * S, ay * S, bx * S, by * S),
                            seg_dist(px, py, cx * S, cy * S, bx * S, by * S))
                    col = WHITE if d < stroke / 2 else base
                    acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]; acc[3] += 255
            n = 4
            row += bytes([acc[0] // n, acc[1] // n, acc[2] // n, acc[3] // n])
        rows.append(row)
    return rows


def main():
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
    os.makedirs(out, exist_ok=True)
    jobs = [
        ("icon-512.png", 512, False),
        ("icon-192.png", 192, False),
        ("icon-180.png", 180, False),
        ("icon-maskable-512.png", 512, True),
    ]
    for name, size, maskable in jobs:
        rows = make_icon(size, maskable)
        write_png(os.path.join(out, name), size, size, rows)
        print(f"  ✓ icons/{name}  {size}x{size}" + ("  maskable" if maskable else ""))


if __name__ == "__main__":
    main()
