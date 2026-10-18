"""Outrun sunset: striped sun, spectrum mountains and an endless neon grid."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ..palette import (CYAN, PINK, WHITE, clamp01, cycle_color, gradient_lut,
                       lerp_color, make_glow, scale_color, vertical_gradient)
from .base import Scene

MOUNTAIN_SEGMENTS = 48


class SunsetGrid(Scene):
    name = "OUTRUN SUNSET"
    tagline = "夕焼けのグリッド"

    def __init__(self):
        super().__init__()
        rng = np.random.default_rng(7)
        self._star_seed = rng.random((150, 3))
        self._jag = rng.random(MOUNTAIN_SEGMENTS + 1) * 0.6 + 0.4
        self._scroll = 0.0
        self._hue = 0.0

    def resize(self, size):
        w, h = size
        self.horizon = hz = int(h * 0.6)
        self.sky = vertical_gradient((w, hz), [(6, 2, 20), (40, 10, 80), (150, 30, 120), (255, 110, 150)])
        self.floor = vertical_gradient((w, h - hz), [(40, 6, 60), (8, 2, 20)])
        self.haze = vertical_gradient((w, 70), [(0, 0, 0), (150, 40, 120), (0, 0, 0)])
        self.sun_r = max(8, int(min(w, h) * 0.26))
        self._sun = self._make_sun(self.sun_r)
        self._glow = make_glow(self.sun_r * 2.8, (255, 70, 150))
        self._stars = [(int(x * w), int(y * hz * 0.7), p) for x, y, p in self._star_seed]

    @staticmethod
    def _make_sun(r: int) -> pygame.Surface:
        d = 2 * r
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        rows = gradient_lut([(255, 245, 130), (255, 160, 90), (255, 70, 150), (200, 40, 190)], d, cyclic=False)
        rgb = pygame.surfarray.pixels3d(surf)
        rgb[:] = rows[None, :, :]
        del rgb
        ax = np.arange(d, dtype=np.float32) - r + 0.5
        dist = np.sqrt(ax[:, None] ** 2 + ax[None, :] ** 2)
        alpha = pygame.surfarray.pixels_alpha(surf)
        alpha[:] = (np.clip((r - dist) * 1.5, 0, 1) * 255).astype(np.uint8)
        del alpha
        return surf

    def draw(self, surf, f, dt):
        w, h = self.size
        hz = self.horizon
        t = f.time
        self._hue += dt * (0.02 + 0.06 * f.intensity)
        self._scroll += dt * (1.2 + 7.0 * f.energy + 5.0 * f.beat_pulse)

        surf.blit(self.sky, (0, 0))

        # twinkling stars, brighter with treble
        for x, y, p in self._stars:
            tw = 0.5 + 0.5 * math.sin(t * (1.5 + p * 3) + p * 40)
            b = clamp01(0.15 + tw * 0.5 + f.treble * 0.7)
            c = scale_color((255, 220, 255), b)
            if p > 0.92:
                pygame.draw.line(surf, c, (x - 2, y), (x + 2, y))
                pygame.draw.line(surf, c, (x, y - 2), (x, y + 2))
            else:
                surf.set_at((x, y), c)

        # the sun: pulses with bass, stripes drift downwards
        cx, cy = w // 2, hz - int(self.sun_r * 0.45)
        glow = self._glow.copy()
        k = int(255 * clamp01(0.35 + 0.5 * f.bass + 0.4 * f.beat_pulse))
        glow.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(glow, glow.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)

        sun = self._sun.copy()
        d = sun.get_height()
        phase = (t * 0.35) % 1.0
        for i in range(7):
            p = (i + phase) / 7
            thick = int(1 + p * d * 0.055 * (1 + 0.8 * f.mid))
            sun.fill((0, 0, 0, 0), (0, int(d * (0.45 + 0.55 * p)), d, thick))
        r = int(self.sun_r * (1.0 + 0.10 * f.bass + 0.05 * f.beat_pulse))
        sun = pygame.transform.smoothscale(sun, (2 * r, 2 * r))
        surf.blit(sun, sun.get_rect(center=(cx, cy)))

        # mountains: bass at the edges, treble near the sun
        nb = len(f.bands)
        edge_col = lerp_color(cycle_color(self._hue + 0.4), WHITE, f.beat_pulse * 0.4)
        pts = [(0, hz)]
        for i in range(MOUNTAIN_SEGMENTS + 1):
            u = i / MOUNTAIN_SEGMENTS
            edge = abs(u - 0.5) * 2
            band = f.bands[int((1 - edge) * (nb - 1))]
            height = (edge ** 1.6) * h * 0.16 * self._jag[i] + band * h * 0.12 * (0.4 + edge)
            pts.append((u * w, hz - height))
        pts.append((w, hz))
        pygame.draw.polygon(surf, (24, 6, 48), pts)
        pygame.draw.lines(surf, edge_col, False, pts[1:-1], 2)

        # floor + perspective grid
        surf.blit(self.floor, (0, hz))
        fh = h - hz
        col = lerp_color(cycle_color(self._hue), WHITE, f.beat_pulse * 0.5)
        dark = (40, 6, 60)
        frac = self._scroll % 1.0
        for i in range(40):
            z = i + 1.0 - frac
            if z < 0.2:
                continue
            y = hz + fh * 0.9 / z
            if y > h:
                continue
            b = clamp01(1.0 - z / 40) ** 1.6
            pygame.draw.line(surf, lerp_color(dark, col, b), (0, y), (w, y), 2 if z < 3 else 1)
        spread = w / 9
        vcol = lerp_color(dark, col, 0.75)
        for i in range(-24, 25):
            pygame.draw.line(surf, vcol, (w / 2 + i * spread * 0.02, hz), (w / 2 + i * spread, h))

        surf.blit(self.haze, (0, hz - 35), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.line(surf, lerp_color(PINK, CYAN, 0.5 + 0.5 * math.sin(t)), (0, hz), (w, hz), 2)
