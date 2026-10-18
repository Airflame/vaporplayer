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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def smoothstep(value: float) -> float:
    value = clamp01(value)
    return value * value * (3 - 2 * value)


def lerp_color(start, end, amount: float) -> tuple[int, int, int]:
    amount = clamp01(amount)
    return (int(start[0] + (end[0] - start[0]) * amount),
            int(start[1] + (end[1] - start[1]) * amount),
            int(start[2] + (end[2] - start[2]) * amount))


def scale_color(color, factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * factor))) for channel in color[:3])


def hsv(hue: float, saturation: float = 1.0, value: float = 1.0) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, clamp01(saturation), clamp01(value))
    return int(red * 255), int(green * 255), int(blue * 255)


def cycle_color(position: float, stops=VAPOR_CYCLE) -> tuple[int, int, int]:
    """Sample a cyclic gradient through `stops`; wraps every 1.0."""
    position = (position % 1.0) * len(stops)
    stop_index = int(position)
    return lerp_color(stops[stop_index % len(stops)], stops[(stop_index + 1) % len(stops)],
                      position - stop_index)


def gradient_lut(stops, count: int = 256, cyclic: bool = True) -> np.ndarray:
    """A (count, 3) uint8 colour table interpolated through `stops`."""
    pts = np.array(stops, dtype=np.float32)
    if cyclic:
        pts = np.vstack([pts, pts[:1]])
    xs = np.linspace(0.0, 1.0, len(pts))
    pos = np.linspace(0.0, 1.0, count, endpoint=not cyclic)
    lut = np.stack([np.interp(pos, xs, pts[:, c]) for c in range(3)], axis=1)
    return lut.astype(np.uint8)


def vertical_gradient(size, stops) -> pygame.Surface:
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    rows = gradient_lut(stops, height, cyclic=False)
    surf = pygame.Surface((width, height))
    pygame.surfarray.blit_array(surf, np.ascontiguousarray(np.broadcast_to(rows[None], (width, height, 3))))
    return surf


def horizontal_gradient(size, stops) -> pygame.Surface:
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    cols = gradient_lut(stops, width, cyclic=False)
    surf = pygame.Surface((width, height))
    pygame.surfarray.blit_array(surf, np.ascontiguousarray(np.broadcast_to(cols[:, None], (width, height, 3))))
    return surf


def make_glow(diameter: int, color, falloff: float = 2.2) -> pygame.Surface:
    """A soft radial glow on black, meant to be blitted with BLEND_RGB_ADD."""
    size = max(2, int(diameter))
    ax = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    dist = np.sqrt(ax[:, None] ** 2 + ax[None, :] ** 2)
    intensity = np.clip(1.0 - dist, 0.0, 1.0) ** falloff
    rgb = (intensity[..., None] * np.array(color, np.float32)[None, None]).astype(np.uint8)
    surf = pygame.Surface((size, size))
    pygame.surfarray.blit_array(surf, rgb)
    return surf


def fullwidth(text: str) -> str:
    """Ｔｕｒｎ ＡＳＣＩＩ ｉｎｔｏ ｔｈｅ ｗｉｄｅ ａｅｓｔｈｅｔｉｃ."""
    out = []
    for ch in text:
        code = ord(ch)
        if ch == " ":
            out.append("　")
        elif 0x21 <= code <= 0x7E:
            out.append(chr(code + 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)
