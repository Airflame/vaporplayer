"""A curving wireframe tunnel whose rings bulge with the spectrum."""
from __future__ import annotations

import math

import pygame

from ..palette import NIGHT, WHITE, clamp01, cycle_color, lerp_color, make_glow, scale_color
from .base import Scene

SIDES = 8
RINGS = 28


class Tunnel(Scene):
    name = "CYBER TUNNEL"
    tagline = "電脳トンネル"

    def __init__(self):
        super().__init__()
        self._travel = 0.0
        self._twist = 0.0

    def resize(self, size):
        self._fade = pygame.Surface(size)
        self._fade.fill(NIGHT)
        self._fade.set_alpha(85)  # leaves motion trails
        self._glow = make_glow(min(size) * 0.6, (170, 60, 255))

    @staticmethod
    def _curve(world_z: float, now: float):
        return (math.sin(world_z * 0.13 + now * 0.21) * 1.3 + math.sin(world_z * 0.05) * 0.8,
                math.cos(world_z * 0.10 + now * 0.17) * 0.9)

    def draw(self, surf, features, dt):
        width, height = self.size
        now = features.time
        self._travel += dt * (2.0 + 9.0 * features.energy + 6.0 * features.beat_pulse)
        self._twist += dt * (0.2 + 0.8 * features.mid)
        surf.blit(self._fade, (0, 0))

        fov = min(width, height) * 0.55
        cam_x, cam_y = self._curve(self._travel, now)
        frac = self._travel % 1.0
        base_id = int(self._travel)
        nb = len(features.bands)

        rings = []
        for k in range(RINGS, 0, -1):  # far to near
            z = k - frac
            if z < 0.25:
                continue
            rid = base_id + k
            ox, oy = self._curve(self._travel + z, now)
            scale = fov / z
            cx = width / 2 + (ox - cam_x) * scale
            cy = height / 2 + (oy - cam_y) * scale
            rot = self._twist + rid * 0.07
            pts = []
            for j in range(SIDES):
                rad = (1.0 + 0.55 * features.bands[(j * 5 + rid * 3) % nb]) * scale
                ang = rot + j * math.tau / SIDES
                pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
            depth = clamp01(1.0 - z / RINGS)
            col = scale_color(cycle_color(rid * 0.04 + now * 0.05), depth ** 1.2 * (0.6 + 0.7 * features.energy))
            if features.beat_pulse > 0.3 and rid % 4 == 0:
                col = lerp_color(col, WHITE, features.beat_pulse * depth)
            rings.append((pts, col, z, cx, cy))

        far = rings[0]
        glow = self._glow.copy()
        glow_level = int(255 * clamp01(0.25 + 0.6 * features.bass + 0.3 * features.beat_pulse))
        glow.fill((glow_level, glow_level, glow_level), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(glow, glow.get_rect(center=(far[3], far[4])), special_flags=pygame.BLEND_RGB_ADD)

        prev = None
        for pts, col, z, _, _ in rings:
            line_width = max(1, min(5, int(2.5 / z) + 1))
            pygame.draw.polygon(surf, col, pts, line_width)
            if prev is not None:
                dim = scale_color(col, 0.6)
                for j in range(0, SIDES, 2):
                    pygame.draw.line(surf, dim, prev[j], pts[j])
            prev = pts
