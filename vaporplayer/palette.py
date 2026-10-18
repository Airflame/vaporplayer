"""Shared colours, gradients and text helpers for the vaporwave look."""
from __future__ import annotations

import colorsys

import numpy as np
import pygame

PINK = (255, 113, 206)
CYAN = (1, 205, 254)
MINT = (5, 255, 161)
LAVENDER = (185, 103, 255)
YELLOW = (255, 251, 150)
PEACH = (255, 160, 122)
INDIGO = (36, 10, 74)
NIGHT = (10, 3, 24)
WHITE = (255, 255, 255)

VAPOR_CYCLE = [PINK, LAVENDER, CYAN, MINT, YELLOW, PEACH]


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def smoothstep(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def lerp_color(a, b, t: float) -> tuple[int, int, int]:
    t = clamp01(t)
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def scale_color(c, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def hsv(h: float, s: float = 1.0, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp01(s), clamp01(v))
    return int(r * 255), int(g * 255), int(b * 255)


def cycle_color(t: float, stops=VAPOR_CYCLE) -> tuple[int, int, int]:
    """Sample a cyclic gradient through `stops`; wraps every 1.0."""
    t = (t % 1.0) * len(stops)
    i = int(t)
    return lerp_color(stops[i % len(stops)], stops[(i + 1) % len(stops)], t - i)


def gradient_lut(stops, n: int = 256, cyclic: bool = True) -> np.ndarray:
    """An (n, 3) uint8 colour table interpolated through `stops`."""
    pts = np.array(stops, dtype=np.float32)
    if cyclic:
        pts = np.vstack([pts, pts[:1]])
    xs = np.linspace(0.0, 1.0, len(pts))
    pos = np.linspace(0.0, 1.0, n, endpoint=not cyclic)
    lut = np.stack([np.interp(pos, xs, pts[:, c]) for c in range(3)], axis=1)
    return lut.astype(np.uint8)


def vertical_gradient(size, stops) -> pygame.Surface:
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    rows = gradient_lut(stops, h, cyclic=False)
    surf = pygame.Surface((w, h))
    pygame.surfarray.blit_array(surf, np.ascontiguousarray(np.broadcast_to(rows[None], (w, h, 3))))
    return surf


def horizontal_gradient(size, stops) -> pygame.Surface:
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    cols = gradient_lut(stops, w, cyclic=False)
    surf = pygame.Surface((w, h))
    pygame.surfarray.blit_array(surf, np.ascontiguousarray(np.broadcast_to(cols[:, None], (w, h, 3))))
    return surf


def make_glow(diameter: int, color, falloff: float = 2.2) -> pygame.Surface:
    """A soft radial glow on black, meant to be blitted with BLEND_RGB_ADD."""
    d = max(2, int(diameter))
    ax = np.linspace(-1.0, 1.0, d, dtype=np.float32)
    dist = np.sqrt(ax[:, None] ** 2 + ax[None, :] ** 2)
    k = np.clip(1.0 - dist, 0.0, 1.0) ** falloff
    rgb = (k[..., None] * np.array(color, np.float32)[None, None]).astype(np.uint8)
    surf = pygame.Surface((d, d))
    pygame.surfarray.blit_array(surf, rgb)
    return surf


def fullwidth(text: str) -> str:
    """Ｔｕｒｎ ＡＳＣＩＩ ｉｎｔｏ ｔｈｅ ｗｉｄｅ ａｅｓｔｈｅｔｉｃ."""
    out = []
    for ch in text:
        o = ord(ch)
        if ch == " ":
            out.append("　")
        elif 0x21 <= o <= 0x7E:
            out.append(chr(o + 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)
