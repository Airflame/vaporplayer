"""Kaleidoscopic plasma, folded into mirrored segments, around a spectrum mandala."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ..palette import CYAN, LAVENDER, MINT, PEACH, PINK, YELLOW, cycle_color, gradient_lut, lerp_color
from .base import Scene

RES = (240, 135)


class Kaleidoscope(Scene):
    name = "DREAM KALEIDOSCOPE"
    tagline = "夢の万華鏡"

    def __init__(self):
        super().__init__()
        width, height = RES
        x = np.linspace(-width / height, width / height, width, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
        gx, gy = np.meshgrid(x, y, indexing="ij")
        self._radius = np.sqrt(gx ** 2 + gy ** 2)
        self._angle = np.arctan2(gy, gx)
        # dark gaps between the neon colours give the plasma its banded, trippy look
        self._lut = gradient_lut([(20, 0, 40), PINK, (60, 10, 90), CYAN, (10, 30, 60), MINT,
                                  (40, 0, 70), YELLOW, (50, 10, 60), LAVENDER, (30, 0, 50), PEACH])
        self._small = pygame.Surface(RES)
        self._phase = 0.0
        self._spin = 0.0
        self._hue = 0.0
        self._ring = 9.0

    def resize(self, size):
        self._scaled = pygame.Surface(size)

    def draw(self, surf, features, dt):
        width, height = self.size
        self._phase += dt * (0.6 + 2.2 * features.energy)
        self._spin += dt * (0.08 + 0.4 * features.mid)
        self._hue += dt * (20 + 90 * features.treble)
        if features.beat:
            self._ring = 0.0
        self._ring += dt * 1.8

        segments = (6, 8, 10)[(features.beat_count // 32) % 3]
        seg = math.tau / segments
        folded_angle = np.abs(((self._angle + self._spin) % seg) - seg / 2)
        radius = self._radius * (1.0 - 0.15 * features.bass)
        u, v = radius * np.cos(folded_angle), radius * np.sin(folded_angle)
        phase = self._phase
        val = (np.sin(u * (7 + 5 * features.bass) - phase * 1.7)
               + np.sin(v * 11 + phase)
               + np.sin(u * 3 - v * 4 + math.sin(phase * 0.37) * 4)
               + np.sin(radius * (9 + 6 * features.mid) - phase * 2.4))
        idx = np.mod(val * 40 + radius * 30 + self._hue, 256).astype(np.uint8)
        rgb = self._lut[idx].astype(np.float32)
        ring = np.exp(-((radius - self._ring) * 6) ** 2) * max(0.0, 1.0 - self._ring / 2.5)
        bright = 0.5 + 0.5 * features.energy + ring * 1.3
        rgb *= bright[..., None]
        pygame.surfarray.blit_array(self._small, np.clip(rgb, 0, 255).astype(np.uint8))
        pygame.transform.smoothscale(self._small, self.size, self._scaled)
        surf.blit(self._scaled, (0, 0))

        # central mandala: the low/mid spectrum mirrored into symmetric petals
        cx, cy = width / 2, height / 2
        base = min(width, height) * 0.11 * (1 + 0.25 * features.bass)
        per_petal = 12
        total = segments * per_petal * 2
        pts = []
        for i in range(total):
            ang = i / total * math.tau - self._spin * 2
            petal_step = i % (per_petal * 2)
            band_index = petal_step if petal_step < per_petal else per_petal * 2 - 1 - petal_step
            rr = base * (1 + 0.9 * features.bands[band_index * 2])
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        pygame.draw.polygon(surf, (12, 0, 28), pts)
        edge = lerp_color(cycle_color(self._hue / 256 + 0.5), (255, 255, 255), features.beat_pulse * 0.6)
        pygame.draw.lines(surf, edge, True, pts, 2)
        pygame.draw.circle(surf, edge, (cx, cy), int(base * 0.55), 1)
