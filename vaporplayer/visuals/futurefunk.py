"""Future funk: a city pop record sleeve come to life. A vinyl spins over a sunburst
above the skyline; colours cut on the bar, and everything moves on held frames like a
looped 80s anime clip."""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from ..palette import WHITE, clamp01, lerp_color, scale_color
from .base import Scene

CJK_FONTS = "yugothicuisemibold,yugothic,meiryo,msgothic,notosanscjkjp,notosansjp,ipagothic,takaogothic"
ANIMATION_FPS = 12    # anime "on twos": the picture holds, then snaps to the next drawing
BEATS_PER_BAR = 4
RAY_COUNT = 18
RPM_DEGREES = 200.0   # 33⅓ rpm, in degrees per second
SCRATCH_TIME = 0.4
SCRATCH_EVERY = 16    # beats between two record scratches
CONFETTI = 26
SPARKLES = 14
INK = (28, 12, 56)    # the hard outline and drop shadow of a cel drawing
VINYL = (22, 16, 34)
WORDS = ["ファンキー", "ディスコ", "ダンス", "グルーヴ", "恋", "真夜中", "フィーバー", "愛"]

# (ray, alternate ray, skyline, accent, second accent)
PALETTES = [
    ((255, 92, 170), (255, 150, 200), (92, 28, 140), (255, 236, 90), (60, 230, 235)),
    ((40, 200, 240), (120, 230, 245), (30, 40, 150), (255, 110, 180), (255, 236, 90)),
    ((255, 200, 50), (255, 228, 120), (214, 40, 120), (70, 60, 220), (255, 255, 255)),
    ((165, 95, 255), (205, 150, 255), (40, 20, 120), (90, 255, 190), (255, 130, 190)),
    ((255, 120, 90), (255, 175, 130), (120, 20, 110), (120, 245, 235), (255, 240, 120)),
]


class FutureFunk(Scene):
    name = "FUTURE FUNK"
    tagline = "真夜中のディスコ"

    def __init__(self):
        super().__init__()
        rng = np.random.default_rng(1984)
        self._confetti = rng.random((CONFETTI, 5)).tolist()  # x, y, phase, spin, shape
        self._sparkles = rng.random((SPARKLES, 3)).tolist()  # x, y, phase
        self._skyline_seed = int(rng.integers(1 << 30))
        font = pygame.font.SysFont(CJK_FONTS, 58, bold=True)
        self._word_images = [self._pop_word(font, word) for word in WORDS]
        self._record_angle = 0.0
        self._scratch = 0.0
        self._next_frame = 0.0

    def resize(self, size):
        width, height = size
        self._canvas = pygame.Surface((max(2, width // 2), max(2, height // 2)))
        canvas_w, canvas_h = self._canvas.get_size()
        self._center = (canvas_w * 0.5, canvas_h * 0.46)
        self._radius = min(canvas_w * 0.22, canvas_h * 0.3)
        self._record = self._press_record(int(self._radius * 2))
        self._halftone = self._print_halftone((canvas_w, canvas_h))
        self._build_skyline(canvas_w, canvas_h)
        self._next_frame = 0.0

    # ------------------------------------------------------------- pre-render
    @staticmethod
    def _pop_word(font, word):
        """A word as a sticker: white letters, a thick ink outline, a hard drop shadow."""
        letters = font.render(word, True, WHITE)
        ink = font.render(word, True, INK)
        margin = 8
        sticker = pygame.Surface((letters.get_width() + margin * 2 + 5, letters.get_height() + margin * 2 + 5),
                                 pygame.SRCALPHA)
        for angle in range(0, 360, 30):
            offset_x = round(math.cos(math.radians(angle)) * 4)
            offset_y = round(math.sin(math.radians(angle)) * 4)
            sticker.blit(ink, (margin + offset_x + 4, margin + offset_y + 4))
            sticker.blit(ink, (margin + offset_x, margin + offset_y))
        sticker.blit(letters, (margin, margin))
        return sticker

    @staticmethod
    def _press_record(diameter):
        radius = diameter // 2
        center = (radius, radius)
        record = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(record, VINYL, center, radius)
        groove_gap = max(3, radius // 22)
        for groove in range(radius - 3, radius // 3, -groove_gap):
            pygame.draw.circle(record, (46, 36, 66), center, groove, 1)
        label_radius = radius // 3
        pygame.draw.circle(record, (255, 236, 90), center, label_radius)
        pygame.draw.circle(record, (255, 92, 170), center, label_radius, max(2, label_radius // 3))
        font = pygame.font.SysFont(CJK_FONTS, max(8, label_radius // 3), bold=True)
        title = font.render("ファンク", True, INK)
        record.blit(title, title.get_rect(center=(radius, radius - label_radius // 3 + 1)))
        pygame.draw.circle(record, VINYL, center, max(2, label_radius // 8))
        return record

    @staticmethod
    def _print_halftone(size):
        """Multiply layer: dots that grow towards the bottom of the sky, like a printed sleeve."""
        width, height = size
        cell = 9
        x_grid, y_grid = np.meshgrid(np.arange(width), np.arange(height), indexing="ij")
        staggered_x = (x_grid + (y_grid // cell % 2) * (cell // 2)) % cell - cell / 2
        offset_y = y_grid % cell - cell / 2
        distance = np.sqrt(staggered_x ** 2 + offset_y ** 2)
        dot_radius = (y_grid / height) ** 1.6 * cell * 0.62
        dots = distance < dot_radius
        pixels = np.full((width, height, 3), 255, np.uint8)
        pixels[dots] = (224, 196, 226)
        layer = pygame.Surface(size)
        pygame.surfarray.blit_array(layer, pixels)
        return layer

    def _build_skyline(self, canvas_w, canvas_h):
        """One skyline per palette, plus the windows that get lit on top of it."""
        rng = random.Random(self._skyline_seed)
        ground = canvas_h
        unit = max(6, canvas_h // 36)
        self._skyline_top = int(canvas_h * 0.52)
        towers = []
        self._windows = []
        left = -unit
        while left < canvas_w:
            tower_w = rng.randint(3, 7) * unit
            tower_h = int(canvas_h * rng.uniform(0.16, 0.42))
            top = ground - tower_h
            towers.append(pygame.Rect(left, top, tower_w, tower_h))
            for row in range(top + unit, ground - unit, unit * 2):
                for column in range(left + unit // 2, left + tower_w - unit, unit):
                    if rng.random() < 0.42:
                        self._windows.append((column, row, rng.randrange(48)))
            left += tower_w - rng.randint(0, 1) * unit
        self._window_size = (max(2, unit // 2), max(2, int(unit * 0.8)))
        self._skylines = []
        for palette in PALETTES:
            skyline = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            for tower in towers:
                skyline.fill(palette[2], tower)
                skyline.fill(scale_color(palette[2], 1.5), (tower.x, tower.y, 2, tower.h))
                skyline.fill(INK, (tower.right - 2, tower.y, 2, tower.h))
                skyline.fill(INK, (tower.x, tower.y, tower.w, 2))
            self._skylines.append(skyline.subsurface((0, self._skyline_top, canvas_w, canvas_h - self._skyline_top)))

    # ------------------------------------------------------------------ draw
    def draw(self, surf, features, dt):
        self._update_record(features, dt)
        self._next_frame -= dt
        if self._next_frame <= 0 or features.beat:
            self._next_frame = 1 / ANIMATION_FPS
            self._draw_frame(self._canvas, features)

        # the only thing that runs at full frame rate: the camera punching in on the beat
        canvas_w, canvas_h = self._canvas.get_size()
        punch = features.beat_pulse ** 2 * 0.05
        crop = pygame.Rect(0, 0, int(canvas_w * (1 - punch)), int(canvas_h * (1 - punch)))
        crop.center = (canvas_w // 2, canvas_h // 2)
        pygame.transform.smoothscale(self._canvas.subsurface(crop), self.size, surf)

    def _update_record(self, features, dt):
        if features.beat and features.beat_count % SCRATCH_EVERY == 0:
            self._scratch = SCRATCH_TIME
        if self._scratch > 0:
            self._scratch = max(0.0, self._scratch - dt)
            speed = -RPM_DEGREES * 4 * math.sin(self._scratch / SCRATCH_TIME * math.tau * 1.5)
        else:
            speed = RPM_DEGREES * (0.35 + 0.65 * clamp01(features.energy * 2))
        self._record_angle = (self._record_angle - speed * dt) % 360

    def _draw_frame(self, canvas, features):
        now = features.time
        palette_index = features.beat_count // (BEATS_PER_BAR * 2) % len(PALETTES)
        ray, alternate, _, accent, second_accent = PALETTES[palette_index]
        center = self._center
        radius = self._radius * (1 + 0.07 * features.bass + 0.05 * features.beat_pulse)

        self._draw_sunburst(canvas, ray, alternate, center, now)
        canvas.blit(self._halftone, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self._draw_confetti(canvas, features, now, accent, second_accent)
        self._draw_spectrum_ring(canvas, features, center, radius, accent, second_accent)
        self._draw_record(canvas, center, radius)
        self._draw_skyline(canvas, palette_index, features, accent)
        self._draw_word(canvas, features)
        self._draw_sparkles(canvas, features, now)

    def _draw_sunburst(self, canvas, ray, alternate, center, now):
        canvas.fill(alternate)
        canvas_w, canvas_h = canvas.get_size()
        reach = canvas_w + canvas_h
        wedge = math.tau / RAY_COUNT
        turn = now * 0.12
        for index in range(0, RAY_COUNT, 2):
            start = index * wedge + turn
            pygame.draw.polygon(canvas, ray, [center,
                                              (center[0] + math.cos(start) * reach, center[1] + math.sin(start) * reach),
                                              (center[0] + math.cos(start + wedge) * reach,
                                               center[1] + math.sin(start + wedge) * reach)])

    def _draw_spectrum_ring(self, canvas, features, center, radius, accent, second_accent):
        bands = features.bands
        band_total = len(bands)
        bar_total = band_total * 2  # mirrored left/right, bass at the bottom
        line_width = max(2, int(radius * math.tau / bar_total * 0.6))
        inner = radius * 1.02
        outer_reach = radius * 0.4
        for layer_offset, use_ink in ((3, True), (0, False)):
            for i in range(bar_total):
                band_index = i if i < band_total else bar_total - 1 - i
                level = float(bands[band_index])
                angle = math.pi / 2 + (i + 0.5) * math.tau / bar_total
                outer = inner + 3 + level * outer_reach
                color = INK if use_ink else lerp_color(accent, second_accent, band_index / band_total)
                pygame.draw.line(canvas, color,
                                 (center[0] + math.cos(angle) * inner + layer_offset,
                                  center[1] + math.sin(angle) * inner + layer_offset),
                                 (center[0] + math.cos(angle) * outer + layer_offset,
                                  center[1] + math.sin(angle) * outer + layer_offset), line_width)

    def _draw_record(self, canvas, center, radius):
        zoom = radius * 2 / self._record.get_width()
        disc = pygame.transform.rotozoom(self._record, self._record_angle, zoom)
        pygame.draw.circle(canvas, INK, (center[0] + 4, center[1] + 4), radius + 2)
        canvas.blit(disc, disc.get_rect(center=(int(center[0]), int(center[1]))))
        # the studio light stays put while the record turns under it
        for start in (-0.95, 2.2):
            arc = [(center[0] + math.cos(start + step * 0.06) * radius * reach,
                    center[1] + math.sin(start + step * 0.06) * radius * reach)
                   for reach, steps in ((0.94, range(7)), (0.42, range(6, -1, -1))) for step in steps]
            pygame.draw.polygon(canvas, (78, 66, 110), arc)

    def _draw_skyline(self, canvas, palette_index, features, accent):
        canvas_h = canvas.get_height()
        bounce = int(features.bass * canvas_h * 0.012)
        canvas.blit(self._skylines[palette_index], (0, self._skyline_top + bounce))
        window_w, window_h = self._window_size
        for x, y, band_index in self._windows:
            if features.bands[band_index] > 0.3:
                canvas.fill(accent, (x, y + bounce, window_w, window_h))

    def _draw_confetti(self, canvas, features, now, accent, second_accent):
        canvas_w, canvas_h = canvas.get_size()
        unit = canvas_h * 0.022 * (1 + 0.5 * features.beat_pulse)
        for index, (piece_x, piece_y, phase, spin_rate, shape) in enumerate(self._confetti):
            x = piece_x * canvas_w
            y = ((piece_y + now * (0.015 + 0.03 * phase)) % 1.0) * canvas_h * 0.7
            spin = now * (spin_rate * 2 - 1) * 1.5 + phase * math.tau
            color = accent if index % 2 else second_accent
            for offset, shade in ((3, INK), (0, color)):
                self._draw_shape(canvas, shape, x + offset, y + offset, unit, spin, shade)

    @staticmethod
    def _draw_shape(canvas, shape, x, y, unit, spin, color):
        """Memphis-style cut-outs: triangles, rings, bars and squiggles."""
        if shape < 0.3:
            corners = [(x + math.cos(spin + corner * math.tau / 3) * unit,
                        y + math.sin(spin + corner * math.tau / 3) * unit) for corner in range(3)]
            pygame.draw.polygon(canvas, color, corners)
        elif shape < 0.55:
            pygame.draw.circle(canvas, color, (x, y), unit * 0.8, max(2, int(unit * 0.35)))
        elif shape < 0.75:
            reach_x, reach_y = math.cos(spin) * unit * 1.2, math.sin(spin) * unit * 1.2
            pygame.draw.line(canvas, color, (x - reach_x, y - reach_y), (x + reach_x, y + reach_y),
                             max(2, int(unit * 0.5)))
        else:
            cosine, sine = math.cos(spin), math.sin(spin)
            squiggle = []
            for step in range(9):
                along = (step / 8 - 0.5) * unit * 3
                across = math.sin(step * 1.6) * unit * 0.5
                squiggle.append((x + along * cosine - across * sine, y + along * sine + across * cosine))
            pygame.draw.lines(canvas, color, False, squiggle, max(2, int(unit * 0.3)))

    def _draw_word(self, canvas, features):
        if features.beat_pulse < 0.2 or features.beat_count % 2:
            return
        word_index = features.beat_count // 2 % len(WORDS)
        canvas_w, canvas_h = canvas.get_size()
        pop = canvas_h / 540 * (0.85 + 0.45 * features.beat_pulse)
        side = 1 if word_index % 2 else -1
        sticker = pygame.transform.rotozoom(self._word_images[word_index], side * -9, pop)
        position = (canvas_w * (0.5 + side * 0.32), canvas_h * 0.17)
        canvas.blit(sticker, sticker.get_rect(center=position).clamp(canvas.get_rect()))

    def _draw_sparkles(self, canvas, features, now):
        canvas_w, canvas_h = canvas.get_size()
        treble = clamp01(features.treble * 1.8)
        for spark_x, spark_y, phase in self._sparkles:
            twinkle = math.sin(now * 5 + phase * 40)
            if twinkle < 0.2:
                continue
            reach = canvas_h * 0.035 * twinkle * (0.4 + treble)
            waist = reach * 0.12
            x, y = spark_x * canvas_w, spark_y * canvas_h * 0.75
            pygame.draw.polygon(canvas, WHITE, [(x, y - reach), (x + waist, y - waist), (x + reach, y),
                                                (x + waist, y + waist), (x, y + reach), (x - waist, y + waist),
                                                (x - reach, y), (x - waist, y - waist)])
