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
        width, height = size
        self.horizon = hz = int(height * 0.6)
        self.sky = vertical_gradient((width, hz), [(6, 2, 20), (40, 10, 80), (150, 30, 120), (255, 110, 150)])
        self.floor = vertical_gradient((width, height - hz), [(40, 6, 60), (8, 2, 20)])
        self.haze = vertical_gradient((width, 70), [(0, 0, 0), (150, 40, 120), (0, 0, 0)])
        self.sun_radius = max(8, int(min(width, height) * 0.26))
        self._sun = self._make_sun(self.sun_radius)
        self._glow = make_glow(self.sun_radius * 2.8, (255, 70, 150))
        self._stars = [(int(x * width), int(y * hz * 0.7), phase) for x, y, phase in self._star_seed]

    @staticmethod
    def _make_sun(radius: int) -> pygame.Surface:
        diameter = 2 * radius
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        rows = gradient_lut([(255, 245, 130), (255, 160, 90), (255, 70, 150), (200, 40, 190)], diameter,
                            cyclic=False)
        rgb = pygame.surfarray.pixels3d(surf)
        rgb[:] = rows[None, :, :]
        del rgb
        ax = np.arange(diameter, dtype=np.float32) - radius + 0.5
        dist = np.sqrt(ax[:, None] ** 2 + ax[None, :] ** 2)
        alpha = pygame.surfarray.pixels_alpha(surf)
        alpha[:] = (np.clip((radius - dist) * 1.5, 0, 1) * 255).astype(np.uint8)
        del alpha
        return surf

    def draw(self, surf, features, dt):
        width, height = self.size
        hz = self.horizon
        now = features.time
        self._hue += dt * (0.02 + 0.06 * features.intensity)
        self._scroll += dt * (1.2 + 7.0 * features.energy + 5.0 * features.beat_pulse)

        surf.blit(self.sky, (0, 0))

        # twinkling stars, brighter with treble
        for x, y, phase in self._stars:
            tw = 0.5 + 0.5 * math.sin(now * (1.5 + phase * 3) + phase * 40)
            brightness = clamp01(0.15 + tw * 0.5 + features.treble * 0.7)
            color = scale_color((255, 220, 255), brightness)
            if phase > 0.92:
                pygame.draw.line(surf, color, (x - 2, y), (x + 2, y))
                pygame.draw.line(surf, color, (x, y - 2), (x, y + 2))
            else:
                surf.set_at((x, y), color)

        # the sun: pulses with bass, stripes drift downwards
        cx, cy = width // 2, hz - int(self.sun_radius * 0.45)
        glow = self._glow.copy()
        glow_level = int(255 * clamp01(0.35 + 0.5 * features.bass + 0.4 * features.beat_pulse))
        glow.fill((glow_level, glow_level, glow_level), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(glow, glow.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)

        sun = self._sun.copy()
        diameter = sun.get_height()
        phase = (now * 0.35) % 1.0
        for i in range(7):
            stripe_pos = (i + phase) / 7
            thick = int(1 + stripe_pos * diameter * 0.055 * (1 + 0.8 * features.mid))
            sun.fill((0, 0, 0, 0), (0, int(diameter * (0.45 + 0.55 * stripe_pos)), diameter, thick))
        radius = int(self.sun_radius * (1.0 + 0.10 * features.bass + 0.05 * features.beat_pulse))
        sun = pygame.transform.smoothscale(sun, (2 * radius, 2 * radius))
        surf.blit(sun, sun.get_rect(center=(cx, cy)))

        # mountains: bass at the edges, treble near the sun
        nb = len(features.bands)
        edge_col = lerp_color(cycle_color(self._hue + 0.4), WHITE, features.beat_pulse * 0.4)
        pts = [(0, hz)]
        for i in range(MOUNTAIN_SEGMENTS + 1):
            u = i / MOUNTAIN_SEGMENTS
            edge = abs(u - 0.5) * 2
            band = features.bands[int((1 - edge) * (nb - 1))]
            peak = (edge ** 1.6) * height * 0.16 * self._jag[i] + band * height * 0.12 * (0.4 + edge)
            pts.append((u * width, hz - peak))
        pts.append((width, hz))
        pygame.draw.polygon(surf, (24, 6, 48), pts)
        pygame.draw.lines(surf, edge_col, False, pts[1:-1], 2)

        # floor + perspective grid
        surf.blit(self.floor, (0, hz))
        fh = height - hz
        col = lerp_color(cycle_color(self._hue), WHITE, features.beat_pulse * 0.5)
        dark = (40, 6, 60)
        frac = self._scroll % 1.0
        for i in range(40):
            z = i + 1.0 - frac
            if z < 0.2:
                continue
            y = hz + fh * 0.9 / z
            if y > height:
                continue
            brightness = clamp01(1.0 - z / 40) ** 1.6
            pygame.draw.line(surf, lerp_color(dark, col, brightness), (0, y), (width, y), 2 if z < 3 else 1)
        spread = width / 9
        vcol = lerp_color(dark, col, 0.75)
        for i in range(-24, 25):
            pygame.draw.line(surf, vcol, (width / 2 + i * spread * 0.02, hz), (width / 2 + i * spread, height))

        surf.blit(self.haze, (0, hz - 35), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.line(surf, lerp_color(PINK, CYAN, 0.5 + 0.5 * math.sin(now)), (0, hz), (width, hz), 2)
