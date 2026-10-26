"""Signalwave: broken late-night transmissions on a CRT in a dark room. The set
surfs between test cards, the weather, an infomercial and a station ident; quiet
music means weak reception (snow, wobble), beats tear the picture and change channel."""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from ..palette import CYAN, PINK, WHITE, YELLOW, clamp01, horizontal_gradient, lerp_color, scale_color, vertical_gradient
from .base import Scene

TV_RES = (320, 240)
MONO_FONTS = "consolas,lucidaconsole,couriernew,dejavusansmono"
HEADLINE_FONTS = "arialblack,impact,arial"
OSD_GREEN = (90, 255, 120)
BLACK = (0, 0, 0)
SMPTE_TOP = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
SMPTE_MIDDLE = [(0, 0, 192), (19, 19, 19), (192, 0, 192), (19, 19, 19), (0, 192, 192), (19, 19, 19), (192, 192, 192)]
SMPTE_BOTTOM = [((0, 33, 76), 1.25), ((235, 235, 235), 1.25), ((50, 0, 106), 1.25), ((19, 19, 19), 1.25),
                ((9, 9, 9), 1 / 3), ((19, 19, 19), 1 / 3), ((29, 29, 29), 1 / 3), ((19, 19, 19), 1.0)]
TICKER = ("   LOCAL FORECAST  ·  CLEAR SKIES OVER THE COAST TONIGHT  ·  LIGHT WINDS FROM THE WEST  ·  "
          "TRAVEL CONDITIONS GOOD  ·  STAY TUNED FOR THE EXTENDED OUTLOOK  ·")
DAYS = ["MON", "TUE", "WED", "THU", "FRI"]
CHANNEL_NUMBERS = [3, 12, 29, 7]  # what the on-screen display calls each programme
OCTAHEDRON = np.array([(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1.3, 0), (0, -1.3, 0)], dtype=float)
OCTAHEDRON_EDGES = [(0, 2), (2, 1), (1, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4), (0, 5), (1, 5), (2, 5), (3, 5)]


def _text(surf, font, text, pos, color, anchor="topleft", shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(font.render(text, True, BLACK), rect.move(1, 1))
    surf.blit(img, rect)
    return rect


class Signalwave(Scene):
    name = "SIGNALWAVE"
    tagline = "深夜の放送"

    def __init__(self):
        super().__init__()
        width, height = TV_RES
        self._content = pygame.Surface(TV_RES)
        self._tv = pygame.Surface(TV_RES)
        self._osd_font = pygame.font.SysFont(MONO_FONTS, 16, bold=True)
        self._small_font = pygame.font.SysFont(MONO_FONTS, 11, bold=True)
        self._title_font = pygame.font.SysFont(HEADLINE_FONTS, 17, bold=True)
        self._headline_font = pygame.font.SysFont(HEADLINE_FONTS, 26, bold=True)

        rng = np.random.default_rng(1999)
        self._snow = []
        for _ in range(6):
            level = (rng.random(TV_RES) ** 1.5 * 255).astype(np.uint8)
            snow = pygame.Surface(TV_RES)
            pygame.surfarray.blit_array(snow, np.repeat(level[..., None], 3, axis=2))
            self._snow.append(snow)
        self._stars = [(int(x * width), int(y * height * 0.45), phase) for x, y, phase in rng.random((40, 3))]

        self._weather_bg = vertical_gradient(TV_RES, [(20, 30, 110), (60, 30, 120)])
        self._weather_header = horizontal_gradient((width, 26), [(0, 90, 200), (40, 20, 120)])
        self._promo_bg = vertical_gradient(TV_RES, [(90, 20, 120), (30, 60, 150), (0, 120, 140)])
        self._ident_bg = vertical_gradient(TV_RES, [(14, 8, 50), (90, 30, 110), (230, 90, 130), (255, 170, 100)])
        self._ticker_img = self._small_font.render(TICKER, True, YELLOW)
        logo_text = pygame.font.SysFont(HEADLINE_FONTS, 96, bold=True).render("7", True, WHITE)
        chrome = vertical_gradient(logo_text.get_size(), [(255, 255, 255), (150, 200, 255), (40, 40, 90),
                                                          (255, 190, 230), (255, 255, 255)])
        self._logo = logo_text.copy()
        self._logo.blit(chrome, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        self._rng = random.Random()
        self._programmes = [self._draw_color_bars, self._draw_weather, self._draw_infomercial,
                            self._draw_station_ident]
        self._channel = 0
        self._on_air = 0.0       # seconds on the current channel
        self._hold = 6.0         # how long before the viewer starts surfing again
        self._static = 0.6       # full static burst between channels, seconds left
        self._osd_timer = 3.0
        self._roll = 0.0         # vertical hold failure, seconds left
        self._roll_offset = 0.0
        self._ticker = 0.0

    def resize(self, size):
        width, height = size
        tv_h = int(height * 0.94)
        tv_w = int(tv_h * 4 / 3)
        if tv_w > width * 0.96:
            tv_w = int(width * 0.96)
            tv_h = int(tv_w * 3 / 4)
        self._tv_rect = pygame.Rect(0, 0, tv_w, tv_h)
        self._tv_rect.center = (width // 2, height // 2)
        self._doubled = pygame.Surface((TV_RES[0] * 2, TV_RES[1] * 2))
        self._screen = pygame.Surface((tv_w, tv_h))
        # rounded CRT corners with a soft dark rim
        radius = int(tv_h * 0.06)
        self._mask = pygame.Surface((tv_w, tv_h), pygame.SRCALPHA)
        self._mask.fill((0, 0, 0, 255))
        pygame.draw.rect(self._mask, (0, 0, 0, 0), self._mask.get_rect(), border_radius=radius)
        for step in range(14):
            pygame.draw.rect(self._mask, (0, 0, 0, 160 - step * 11), self._mask.get_rect().inflate(-2 * step, -2 * step),
                             width=1, border_radius=max(1, radius - step))

    # ------------------------------------------------------------------ draw
    def draw(self, surf, features, dt):
        now = features.time
        width, height = TV_RES
        self._on_air += dt
        quality = clamp01(0.3 + features.intensity * 1.6)  # quiet music = weak reception
        if self._on_air > self._hold and features.beat:
            self._switch_channel()
        if features.beat and self._rng.random() < 0.06 and self._roll <= 0:
            self._roll = 0.7

        self._programmes[self._channel](self._content, features, now, dt)

        # the signal: vertical roll, per-line wobble, ghosting and snow
        tv = self._tv
        tv.fill(BLACK)
        if self._roll > 0:
            self._roll -= dt
            self._roll_offset = (self._roll_offset + dt * 420) % height
        else:
            self._roll_offset = 0.0
        jitter = (1 - quality) * 3 + features.beat_pulse * 5
        strip = 2
        for y in range(0, height, strip):
            shift = int(math.sin(y * 0.13 + now * 9) * jitter * 0.5 + (self._rng.random() - 0.5) * jitter)
            source_y = (y + int(self._roll_offset)) % height
            tv.blit(self._content, (shift, y), (0, source_y, width, strip))
        if self._roll > 0:
            tv.fill(BLACK, (0, (height - int(self._roll_offset)) % height, width, 10))
        ghost = tv.copy()
        ghost.set_alpha(38)
        tv.blit(ghost, (4, 0))
        if self._static > 0:
            self._static -= dt
        snow_alpha = int(255 * clamp01((1 - quality) * 0.55 + max(0.0, self._static) / 0.35))
        if snow_alpha > 4:
            snow = self._rng.choice(self._snow)
            snow.set_alpha(snow_alpha)
            tv.blit(snow, (0, 0))
        self._draw_osd(tv, now, dt)  # drawn by the set itself, so the bad signal doesn't touch it

        pygame.transform.scale(tv, self._doubled.get_size(), self._doubled)
        pygame.transform.smoothscale(self._doubled, self._tv_rect.size, self._screen)
        self._screen.blit(self._mask, (0, 0))
        surf.fill(scale_color(pygame.transform.average_color(tv), 0.22))  # the room, lit by the screen
        surf.blit(self._screen, self._tv_rect)

    def _switch_channel(self):
        self._channel = self._rng.choice([index for index in range(len(self._programmes)) if index != self._channel])
        self._on_air = 0.0
        self._hold = self._rng.uniform(5.0, 11.0)
        self._static = 0.35
        self._osd_timer = 2.5

    def _draw_osd(self, tv, now, dt):
        width, height = TV_RES
        if self._osd_timer > 0:
            self._osd_timer -= dt
            _text(tv, self._osd_font, f"CH {CHANNEL_NUMBERS[self._channel]:02d}", (width - 12, 10), OSD_GREEN,
                  anchor="topright")
        rect = _text(tv, self._osd_font, "PLAY", (12, height - 26), OSD_GREEN)
        triangle_x = rect.right + 6
        pygame.draw.polygon(tv, OSD_GREEN, [(triangle_x, rect.top + 3), (triangle_x, rect.bottom - 3),
                                            (triangle_x + 8, rect.centery)])
        seconds = int(now)
        counter = f"SP {seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        _text(tv, self._osd_font, counter, (width - 12, height - 26), OSD_GREEN, anchor="topright")

    # ------------------------------------------------------------ programmes
    def _draw_color_bars(self, content, features, now, dt):
        width, height = TV_RES
        bar_w = width / 7
        top_h, middle_h = int(height * 0.67), int(height * 0.08)
        boost = 0.85 + 0.15 * features.beat_pulse
        for i, color in enumerate(SMPTE_TOP):
            content.fill(scale_color(color, boost), (int(i * bar_w), 0, int(bar_w) + 1, top_h))
        for i, color in enumerate(SMPTE_MIDDLE):
            content.fill(scale_color(color, boost), (int(i * bar_w), top_h, int(bar_w) + 1, middle_h))
        left = 0.0
        for color, units in SMPTE_BOTTOM:
            content.fill(color, (int(left), top_h + middle_h, int(units * bar_w) + 1, height - top_h - middle_h))
            left += units * bar_w
        if now % 1.6 < 1.1:
            box = pygame.Rect(0, 0, 200, 48)
            box.center = (width // 2, top_h // 2)
            content.fill((10, 10, 40), box)
            pygame.draw.rect(content, WHITE, box, 1)
            _text(content, self._osd_font, "PLEASE STAND BY", (box.centerx, box.y + 8), WHITE, anchor="midtop")
            meter = box.w - 24
            content.fill((30, 30, 60), (box.x + 12, box.bottom - 13, meter, 6))
            content.fill(OSD_GREEN, (box.x + 12, box.bottom - 13, int(meter * clamp01(features.bass)), 6))

    def _draw_weather(self, content, features, now, dt):
        width, height = TV_RES
        content.blit(self._weather_bg, (0, 0))
        content.blit(self._weather_header, (0, 12))
        _text(content, self._title_font, "LOCAL FORECAST", (10, 14), YELLOW)
        nb = len(features.bands)
        for i, day in enumerate(DAYS):
            band = features.bands[(i * 8 + 2) % nb]
            panel = pygame.Rect(12 + i * 60, 48, 54, 128)
            content.fill((30, 50, 140), panel)
            pygame.draw.rect(content, (120, 160, 255), panel, 1)
            _text(content, self._small_font, day, (panel.centerx, panel.y + 4), YELLOW, anchor="midtop")
            icon_y = panel.y + 34
            if band > 0.45:
                pygame.draw.circle(content, (255, 220, 60), (panel.centerx, icon_y), 9)
                for ray in range(8):
                    angle = ray * math.tau / 8 + now * 0.5
                    pygame.draw.line(content, (255, 220, 60),
                                     (panel.centerx + math.cos(angle) * 12, icon_y + math.sin(angle) * 12),
                                     (panel.centerx + math.cos(angle) * 15, icon_y + math.sin(angle) * 15))
            else:
                for offset_x, offset_y, radius in ((-6, 2, 7), (4, 0, 9), (12, 3, 6)):
                    pygame.draw.circle(content, (225, 230, 245), (panel.centerx - 3 + offset_x, icon_y + offset_y), radius)
            _text(content, self._osd_font, f"{58 + int(band * 40)}°", (panel.centerx, panel.y + 52), WHITE,
                  anchor="midtop")
            bar_h = int(band * 44)
            if bar_h > 0:
                content.fill(lerp_color(CYAN, PINK, band), (panel.x + 10, panel.bottom - 6 - bar_h, panel.w - 20, bar_h))
        self._ticker += dt * 40
        strip_y = height - 52
        content.fill((10, 10, 60), (0, strip_y, width, 18))
        ticker_w = self._ticker_img.get_width()
        ticker_x = -int(self._ticker % ticker_w)
        content.blit(self._ticker_img, (ticker_x, strip_y + 3))
        content.blit(self._ticker_img, (ticker_x + ticker_w, strip_y + 3))
        minutes = (14 + int(now // 60)) % 60
        clock = f"3{':' if now % 1 < 0.5 else ' '}{minutes:02d} AM"
        clock_box = pygame.Rect(width - 74, strip_y - 1, 74, 20)
        content.fill((0, 60, 160), clock_box)
        _text(content, self._osd_font, clock, clock_box.center, WHITE, anchor="center")

    def _draw_infomercial(self, content, features, now, dt):
        width, height = TV_RES
        content.blit(self._promo_bg, (0, 0))

        # the product: a spinning crystal
        spin = now * (1.0 + 2.0 * features.energy)
        tilt = 0.4
        rotate_y = np.array([[math.cos(spin), 0, math.sin(spin)], [0, 1, 0], [-math.sin(spin), 0, math.cos(spin)]])
        rotate_x = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
        vertices = OCTAHEDRON @ rotate_y.T @ rotate_x.T
        size = 40 * (1 + 0.15 * features.bass)
        points = [(95 + vx * size, 105 - vy * size) for vx, vy, _ in vertices.tolist()]
        for start, end in OCTAHEDRON_EDGES:
            pygame.draw.line(content, lerp_color(CYAN, WHITE, 0.5), points[start], points[end], 2)
        if features.beat_pulse > 0.5:  # the obligatory sparkle
            sparkle_x, sparkle_y = points[4]
            reach = 10 * features.beat_pulse
            pygame.draw.line(content, WHITE, (sparkle_x - reach, sparkle_y), (sparkle_x + reach, sparkle_y))
            pygame.draw.line(content, WHITE, (sparkle_x, sparkle_y - reach), (sparkle_x, sparkle_y + reach))

        # "NEW!" starburst
        burst_x, burst_y = 262, 44
        radius = 30 * (1 + 0.2 * features.beat_pulse + 0.1 * features.bass)
        burst = []
        for point in range(16):
            angle = point * math.tau / 16 + now * 0.6
            reach = radius if point % 2 == 0 else radius * 0.7
            burst.append((burst_x + math.cos(angle) * reach, burst_y + math.sin(angle) * reach))
        pygame.draw.polygon(content, YELLOW, burst)
        pygame.draw.polygon(content, (220, 30, 40), burst, 2)
        _text(content, self._title_font, "NEW!", (burst_x, burst_y), (220, 30, 40), anchor="center", shadow=False)

        _text(content, self._small_font, "ONLY", (190, 92), WHITE)
        _text(content, self._headline_font, "$19.99", (186, 104), YELLOW)
        banner = pygame.Rect(0, 160, width, 34)
        content.fill((235, 30, 50) if features.beat_count % 2 else (170, 10, 30), banner)
        _text(content, self._headline_font, "CALL NOW!", banner.center, WHITE, anchor="center")
        _text(content, self._osd_font, "1-800-555-0199", (width // 2, banner.bottom + 4), YELLOW, anchor="midtop")

    def _draw_station_ident(self, content, features, now, dt):
        width, height = TV_RES
        content.blit(self._ident_bg, (0, 0))
        for x, y, phase in self._stars:
            level = int(140 + 115 * math.sin(now * 2 + phase * 20))
            content.set_at((x, y), (level, level, level))
        horizon = int(height * 0.7)
        for line in range(6):  # a little outrun floor under the logo
            line_y = horizon + int((line / 6) ** 1.8 * (height - horizon))
            content.fill((255, 90, 170), (0, line_y, width, 1))

        spin = now * (0.8 + 1.5 * features.mid)
        squash = math.cos(spin)
        logo_w = max(1, int(self._logo.get_width() * abs(squash)))
        logo = pygame.transform.scale(self._logo, (logo_w, self._logo.get_height()))
        if squash < 0:  # the back of the logo is in shadow
            logo.fill((150, 140, 180), special_flags=pygame.BLEND_RGB_MULT)
        content.blit(logo, logo.get_rect(center=(width // 2, 92)))
        _text(content, self._title_font, "CHANNEL 7", (width // 2, 150), WHITE, anchor="midtop")
        _text(content, self._small_font, "LATE NIGHT", (width // 2, 172), PINK, anchor="midtop")
        if features.beat_count % 4 < 2:
            _text(content, self._small_font, "STAY TUNED", (width // 2, 186), YELLOW, anchor="midtop")
