"""Dreampunk: a rain-drenched neon megacity at night, after the Dream Catalogue
aesthetic and 2814's "Birth of a New Day". The neon runs from cold blue in calm
passages through violet and magenta to hot pink and amber at full intensity."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
import pygame

from ..palette import WHITE, clamp01, gradient_lut, lerp_color, make_glow, scale_color, vertical_gradient
from .base import Scene

# neon colour by musical heat: calm -> intense
NEON_HEAT = [(30, 70, 255), (0, 190, 255), (140, 80, 255), (255, 60, 200), (255, 40, 90), (255, 150, 40)]
SIGN_WORDS = ["夢", "雨夜", "電脳街", "新しい日", "誕生", "未来", "夜明け", "東京"]
SIGN_WORDS_LATIN = ["DREAM", "RAIN", "NEON", "NEWDAY", "CITY", "NIGHT", "DAWN", "2814"]
CJK_FONTS = "msgothic,yugothic,meiryo,notosanscjkjp,notosansjp,ipagothic,takaogothic"
BLACK = (0, 0, 0)
RAIN_DROPS = 700
RAIN_SLANT = 0.18  # horizontal drift per unit of fall
BOKEH_COUNT = 14


@dataclass
class NeonSign:
    core: pygame.Surface  # white lettering on black, blitted additively
    halo: pygame.Surface  # soft light the panel casts on the wall around it
    box: pygame.Rect      # the sign's backing panel
    heat_offset: float    # signs sit at slightly different points of the heat palette
    band: int             # spectrum band that drives its brightness
    flicker_phase: float


def _supports(font: pygame.font.Font, text: str) -> bool:
    return all(glyph_metrics is not None for glyph_metrics in font.metrics(text))


def _render_vertical(font: pygame.font.Font, text: str) -> pygame.Surface:
    glyphs = [font.render(char, True, WHITE, BLACK) for char in text if char != " "]
    width = max(glyph.get_width() for glyph in glyphs)
    step = [int(glyph.get_height() * 0.92) for glyph in glyphs]
    surf = pygame.Surface((width, sum(step)))
    surf.fill(BLACK)
    top = 0
    for glyph, advance in zip(glyphs, step):
        surf.blit(glyph, ((width - glyph.get_width()) // 2, top))
        top += advance
    return surf


def _panel_glow(panel_size, margin: int) -> pygame.Surface:
    """Light spilling from a sign panel onto the wall: a white panel blurred `margin` px outwards."""
    canvas = pygame.Surface((panel_size[0] + 2 * margin, panel_size[1] + 2 * margin))
    canvas.fill(BLACK)
    canvas.fill(WHITE, (margin, margin, panel_size[0], panel_size[1]))
    size = canvas.get_size()
    small = pygame.transform.smoothscale(canvas, (max(1, size[0] // 10), max(1, size[1] // 10)))
    return pygame.transform.smoothscale(small, size)


class Dreampunk(Scene):
    name = "DREAMPUNK"
    tagline = "雨の電脳都市"

    def __init__(self):
        super().__init__()
        self._heat_lut = gradient_lut(NEON_HEAT, 256, cyclic=False)
        self._heat = 0.2
        self._ripples: list[list[float]] = []  # [x, y, age]
        self._rng = random.Random()

    def _neon(self, heat: float) -> tuple[int, int, int]:
        return tuple(int(channel) for channel in self._heat_lut[int(clamp01(heat) * 255)])

    # ------------------------------------------------------------------ build
    def resize(self, size):
        width, height = size
        rng = np.random.default_rng(2814)  # the same city every time
        self.street_y = street_y = int(height * 0.74)
        self._sky = vertical_gradient((width, street_y), [(2, 3, 12), (8, 10, 30), (24, 18, 50)])
        self._street = vertical_gradient((width, height - street_y), [(14, 12, 26), (4, 4, 10)])
        haze = make_glow(512, (255, 255, 255), falloff=1.4)
        self._haze = pygame.transform.smoothscale(haze, (int(width * 1.1), int(street_y * 0.9)))
        fog = vertical_gradient((width, int(height * 0.2)), [(0, 0, 0), (60, 60, 70), (0, 0, 0)])
        self._fog = fog

        self._far, self._antennas = self._build_far_skyline(rng, width, street_y)
        self._near = self._build_near_buildings(rng, width, height, street_y)
        self._signs = self._build_signs(rng, width, height, street_y)
        billboard_w = int(width * 0.16)
        self._billboard = pygame.Rect(width // 2 - billboard_w // 2, int(street_y * 0.42), billboard_w,
                                      int(height * 0.07))

        self._drop_x = rng.uniform(0, width * 1.2, RAIN_DROPS)
        self._drop_y = rng.uniform(0, height, RAIN_DROPS)
        self._drop_speed = rng.uniform(0.9, 1.6, RAIN_DROPS) * height
        self._drop_len = rng.uniform(0.012, 0.035, RAIN_DROPS) * height

        unit = min(width, height)
        self._bokeh_glows = [make_glow(unit * scale, (255, 255, 255), falloff=1.2) for scale in (0.08, 0.13, 0.2)]
        self._bokeh = rng.random((BOKEH_COUNT, 4))  # x, y, size class, heat offset

    @staticmethod
    def _build_far_skyline(rng, width, street_y):
        layer = pygame.Surface((width, street_y), pygame.SRCALPHA)
        antennas = []
        left = -20
        while left < width:
            tower_w = int(rng.uniform(0.025, 0.06) * width)
            top = int(street_y * (1 - rng.uniform(0.22, 0.62)))
            layer.fill((16, 15, 34, 255), (left, top, tower_w, street_y - top))
            for wy in range(top + 6, street_y - 4, 7):
                for wx in range(left + 3, left + tower_w - 3, 6):
                    if rng.random() < 0.13:
                        tone = (95, 85, 60, 255) if rng.random() < 0.5 else (60, 90, 125, 255)
                        layer.fill(tone, (wx, wy, 2, 2))
            if rng.random() < 0.3:
                mast = int(rng.uniform(0.03, 0.08) * street_y)
                mx = left + tower_w // 2
                pygame.draw.line(layer, (30, 28, 50, 255), (mx, top), (mx, top - mast))
                antennas.append((mx, top - mast))
            left += int(tower_w * rng.uniform(0.7, 1.05))
        return layer, antennas

    @staticmethod
    def _build_near_buildings(rng, width, height, street_y):
        layer = pygame.Surface((width, street_y), pygame.SRCALPHA)
        for side in (0, 1):
            edge = 0
            while edge < width * 0.24:
                block_w = int(rng.uniform(0.07, 0.12) * width)
                top = int(rng.uniform(-0.1, 0.22) * height)
                left = edge if side == 0 else width - edge - block_w
                rect = pygame.Rect(left, top, block_w, street_y - top)
                layer.fill((7, 6, 16, 255), rect)
                rim_x = rect.right - 1 if side == 0 else rect.left
                pygame.draw.line(layer, (40, 38, 70, 255), (rim_x, max(0, top)), (rim_x, street_y))
                for wy in range(max(0, top) + 10, street_y - 8, 14):
                    for wx in range(rect.left + 6, rect.right - 8, 11):
                        if rng.random() < 0.07:
                            layer.fill((110, 95, 70, 255), (wx, wy, 4, 6))
                edge += int(block_w * 0.8)
        return layer

    def _build_signs(self, rng, width, height, street_y) -> list[NeonSign]:
        size = max(12, int(height * 0.042))
        font = pygame.font.SysFont(CJK_FONTS, size, bold=True)
        words = SIGN_WORDS if _supports(font, "".join(SIGN_WORDS)) else SIGN_WORDS_LATIN
        signs: list[NeonSign] = []
        taken: list[pygame.Rect] = []
        for word in words:
            core = _render_vertical(font, word)
            pad = max(4, size // 5)
            box = pygame.Rect(0, 0, core.get_width() + 2 * pad, core.get_height() + 2 * pad)
            for _ in range(30):  # find a free spot on one of the near buildings
                if rng.random() < 0.5:
                    box.x = int(rng.uniform(0.02, 0.26) * width - box.w / 2)
                else:
                    box.x = int(rng.uniform(0.74, 0.98) * width - box.w / 2)
                box.y = int(rng.uniform(0.06 * height, max(0.07 * height, street_y - box.h - 0.05 * height)))
                if not any(box.inflate(16, 16).colliderect(other) for other in taken):
                    break
            taken.append(box.copy())
            signs.append(NeonSign(core=core, halo=_panel_glow(box.size, int(size * 1.6)), box=box.copy(),
                                  heat_offset=float(rng.uniform(-0.15, 0.15)), band=int(rng.integers(4, 40)),
                                  flicker_phase=float(rng.uniform(0, math.tau))))
        return signs

    # ------------------------------------------------------------------ draw
    def draw(self, surf, features, dt):
        width, height = self.size
        street_y = self.street_y
        now = features.time

        target = clamp01(features.intensity * 1.8 + features.energy * 0.5)
        self._heat += (target - self._heat) * (1.0 - math.exp(-dt * 1.5))
        heat = clamp01(self._heat + features.beat_pulse * 0.12)
        neon = self._neon(heat)

        # sky, and the city's glow reflected in the smog
        surf.blit(self._sky, (0, 0))
        haze = self._haze.copy()
        haze.fill(scale_color(neon, 0.35 + 0.3 * features.bass + 0.25 * features.beat_pulse),
                  special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(haze, haze.get_rect(center=(width // 2, street_y)), special_flags=pygame.BLEND_RGB_ADD)

        surf.blit(self._far, (0, 0))
        if features.beat_count % 2 == 0:  # aircraft warning lights blink with the beat
            for ax, ay in self._antennas:
                pygame.draw.circle(surf, (255, 50, 60), (ax, ay), 2)
        self._draw_billboard(surf, features, heat)
        surf.blit(self._near, (0, 0))
        for sign in self._signs:
            self._draw_sign(surf, sign, features, heat, now)

        fog = self._fog.copy()
        fog.fill(lerp_color((200, 200, 220), neon, 0.5), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(fog, (0, street_y - fog.get_height() // 2 - 10), special_flags=pygame.BLEND_RGB_ADD)

        self._draw_street(surf, features, neon, now, dt)
        self._draw_rain(surf, features, neon, dt)
        self._draw_bokeh(surf, features, heat, now, dt)

    def _draw_billboard(self, surf, features, heat):
        rect = self._billboard
        color = self._neon(heat + 0.12)
        surf.fill((6, 4, 14), rect)
        bars = 24
        bar_w = rect.w / bars
        nb = len(features.bands)
        for i in range(bars):
            level = features.bands[int(i * nb / bars)]
            bar_h = int(level * (rect.h - 6))
            if bar_h > 0:
                surf.fill(scale_color(color, 0.5 + 0.5 * level),
                          (int(rect.x + i * bar_w) + 1, rect.bottom - 3 - bar_h, max(1, int(bar_w) - 2), bar_h))
        pygame.draw.rect(surf, scale_color(color, 0.8), rect, 1)

    def _draw_sign(self, surf, sign: NeonSign, features, heat, now):
        level = clamp01(0.45 + 0.8 * features.bands[sign.band])
        # an old tube stutters now and then
        if math.sin(now * 7.3 + sign.flicker_phase) * math.sin(now * 3.1 + sign.flicker_phase * 2) > 0.85:
            level *= 0.25
        color = self._neon(heat + sign.heat_offset)
        halo = sign.halo.copy()
        halo.fill(scale_color(color, level * 0.9), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(halo, halo.get_rect(center=sign.box.center), special_flags=pygame.BLEND_RGB_ADD)
        surf.fill((8, 6, 18), sign.box)
        pygame.draw.rect(surf, scale_color(color, level), sign.box, 2)
        core = sign.core.copy()
        core.fill(scale_color(lerp_color(color, WHITE, 0.55), level), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(core, core.get_rect(center=sign.box.center), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_street(self, surf, features, neon, now, dt):
        width, height = self.size
        street_y = self.street_y
        reflect_h = min(height - street_y, street_y)
        mirrored = pygame.transform.flip(surf.subsurface((0, street_y - reflect_h, width, reflect_h)), False, True)
        mirrored.fill((95, 105, 135), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(self._street, (0, street_y))
        strip = 3
        wobble = 0.6 + features.energy
        for row in range(0, reflect_h, strip):
            depth = row / reflect_h
            offset = int(math.sin(row * 0.35 + now * 4.0) * (1 + 7 * depth) * wobble)
            surf.blit(mirrored, (offset, street_y + row), (0, row, width, strip), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.line(surf, scale_color(neon, 0.5), (0, street_y), (width, street_y))

        # raindrop ripples in the puddles, busier when the music is
        spawn = dt * (6 + 30 * features.energy)
        while spawn > 0:
            if self._rng.random() < spawn:
                self._ripples.append([self._rng.uniform(0, width), self._rng.uniform(street_y + 6, height), 0.0])
            spawn -= 1
        alive = []
        for ripple in self._ripples:
            ripple[2] += dt
            if ripple[2] < 0.8:
                alive.append(ripple)
                depth = (ripple[1] - street_y) / max(1, height - street_y)
                radius = (4 + 40 * ripple[2]) * (0.4 + depth)
                fade = 1.0 - ripple[2] / 0.8
                rect = pygame.Rect(0, 0, int(radius * 2), max(2, int(radius * 0.6)))
                rect.center = (int(ripple[0]), int(ripple[1]))
                pygame.draw.ellipse(surf, scale_color(neon, 0.6 * fade), rect, 1)
        self._ripples = alive[-80:]

    def _draw_rain(self, surf, features, neon, dt):
        width, height = self.size
        active = int(250 + 450 * clamp01(features.energy * 1.5))
        fall = self._drop_speed * dt * (1.0 + 0.6 * features.energy)
        self._drop_y += fall
        self._drop_x -= fall * RAIN_SLANT
        wrapped = self._drop_y > height
        self._drop_y[wrapped] -= height + self._drop_len[wrapped]
        self._drop_x[wrapped] = np.random.uniform(0, width * 1.2, int(wrapped.sum()))
        color = lerp_color((120, 130, 165), neon, 0.3)
        for x, y, length in zip(self._drop_x[:active].tolist(), self._drop_y[:active].tolist(),
                                self._drop_len[:active].tolist()):
            pygame.draw.line(surf, color, (x, y), (x + RAIN_SLANT * length, y - length))

    def _draw_bokeh(self, surf, features, heat, now, dt):
        """Out-of-focus lights, as if seen through a rain-streaked window."""
        width, height = self.size
        self._bokeh[:, 1] += dt * 0.012  # slowly sliding down the glass
        self._bokeh[self._bokeh[:, 1] > 1.1, 1] = -0.1
        for bx, by, size_class, offset in self._bokeh.tolist():
            glow = self._bokeh_glows[int(size_class * 2.999)].copy()
            pulse = 0.25 + 0.35 * features.bass + 0.15 * math.sin(now * 0.7 + offset * 20)
            glow.fill(scale_color(self._neon(heat + (offset - 0.5) * 0.4), pulse),
                      special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(glow, glow.get_rect(center=(int(bx * width), int(by * height))),
                      special_flags=pygame.BLEND_RGB_ADD)
