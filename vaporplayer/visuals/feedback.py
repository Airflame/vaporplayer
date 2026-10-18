"""Milkdrop-style video feedback: each frame zooms and rotates the last one,
leaving colour-shifting echoes of a waveform halo and a breathing wire globe."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ..palette import cycle_color
from .base import Scene

LAT, LON = 9, 18


class LiquidMemory(Scene):
    name = "LIQUID MEMORY"
    tagline = "液体の記憶"

    def __init__(self):
        super().__init__()
        lat = np.linspace(-np.pi / 2 * 0.85, np.pi / 2 * 0.85, LAT)
        lon = np.linspace(0, 2 * np.pi, LON, endpoint=False)
        la, lo = np.meshgrid(lat, lon, indexing="ij")
        self._sphere = np.stack([np.cos(la) * np.cos(lo), np.sin(la), np.cos(la) * np.sin(lo)], axis=-1)
        self._rows = np.linspace(0, 30, LAT).astype(int)

    def resize(self, size):
        w, h = size
        self._canvas = pygame.Surface((max(2, w // 2), max(2, h // 2)))
        self._scaled = pygame.Surface(size)

    def draw(self, surf, f, dt):
        c = self._canvas
        cw, ch = c.get_size()
        t = f.time

        # feedback: warp the previous frame outwards and let it decay with a drifting tint
        zoom = 1.01 + 0.04 * f.bass + 0.03 * f.beat_pulse
        angle = math.sin(t * 0.17) * (0.8 + 3.0 * f.mid)
        warped = pygame.transform.rotozoom(c, angle, zoom)
        c.blit(warped, warped.get_rect(center=(cw // 2, ch // 2)))
        k = 0.5 * t
        tint = tuple(int(240 + 7 * math.sin(k + o)) for o in (0.0, 2.1, 4.2))
        c.fill(tint, special_flags=pygame.BLEND_RGB_MULT)

        cx, cy = cw / 2, ch / 2
        unit = min(cw, ch)

        # polar oscilloscope halo
        n = len(f.wave_left)
        ang = np.linspace(0, math.tau, n, endpoint=False) + t * 0.3
        rad = unit * (0.28 + 0.06 * f.bass) + f.wave_left * unit * 0.22
        halo = np.column_stack([cx + np.cos(ang) * rad, cy + np.sin(ang) * rad]).tolist()
        pygame.draw.lines(c, cycle_color(t * 0.06), True, halo, 2)

        # goniometer: mono shows as a vertical line, stereo blooms sideways
        gx = cx + (f.wave_left - f.wave_right) * unit * 0.25
        gy = cy - (f.wave_left + f.wave_right) * unit * 0.25
        pygame.draw.lines(c, cycle_color(t * 0.06 + 0.5), False, np.column_stack([gx, gy]).tolist(), 1)

        # wire globe, latitudes displaced by their band
        disp = 1.0 + 0.7 * f.bands[self._rows][:, None, None]
        v = self._sphere * disp
        ay, ax = t * 0.4, t * 0.23 + 0.4
        ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
        rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
        v = v @ ry.T @ rx.T
        scale = unit * (0.16 + 0.05 * f.bass) * 3.0 / (v[..., 2] + 3.0)
        proj = np.stack([cx + v[..., 0] * scale, cy + v[..., 1] * scale], axis=-1)
        col_a = cycle_color(t * 0.05 + 0.25)
        col_b = cycle_color(t * 0.05 + 0.6)
        for i in range(LAT):
            pygame.draw.lines(c, col_a, True, proj[i].tolist(), 1)
        for j in range(LON):
            pygame.draw.lines(c, col_b, False, proj[:, j].tolist(), 1)

        if f.beat:  # the feedback zoom turns this into an expanding shockwave
            pygame.draw.circle(c, (255, 240, 255), (cx, cy), int(unit * 0.42), 2)

        pygame.transform.smoothscale(c, self.size, self._scaled)
        surf.blit(self._scaled, (0, 0))
