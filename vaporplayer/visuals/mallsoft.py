"""Mallsoft: drifting through an endless, empty 80s/90s shopping mall after closing
time. Pastel tiles, backlit store signs, palms and fountains under a skylight, all
softened by bloom and ghosting into a hazy, half-remembered dream."""
from __future__ import annotations

import math

import numpy as np
import pygame

from ..palette import clamp01, lerp_color, scale_color, vertical_gradient
from .base import Scene

CREAM = (250, 236, 222)
BLUSH = (255, 182, 208)
SEAFOAM = (128, 222, 208)
LILAC = (200, 172, 255)
APRICOT = (255, 202, 160)
POWDER = (165, 205, 255)
SPEARMINT = (190, 250, 200)
HAZE = (236, 208, 228)  # what everything dissolves into with distance
LABEL_INK = (80, 40, 90)
AFTER_HOURS = (178, 160, 190)  # dims the whole mall to a dusky, lavender-tinted closing time
STORE_COLORS = [BLUSH, SEAFOAM, LILAC, APRICOT, POWDER, SPEARMINT]
STORES = ["FOOD COURT", "ARCADE", "RECORDS", "VIDEO RENTAL", "CINEMA", "COSMETICS", "FASHION", "TOYS",
          "SALE 50%", "ELECTRONICS", "PERFUME", "CAFE", "JEWELRY", "PHOTO 1 HR", "BOOKS", "SPORTS"]
LABEL_FONTS = "arialroundedmtbold,verdana,trebuchetms,arial"

# world layout (camera at origin looking down +z)
FLOOR_Y = -0.55
BALCONY_Y = 0.42
CEILING_Y = 1.2
WALL_X = 1.0
BALCONY_X = 0.78
NEAR = 0.35
FAR = 15.0
TILE = 0.5
PROP_SPACING = 2.0
MOTES = 90


class Mallsoft(Scene):
    name = "MALLSOFT"
    tagline = "閉店後のショッピングモール"

    def __init__(self):
        super().__init__()
        self._travel = 0.0
        self._motes = np.random.default_rng(1987).random((MOTES, 3))  # x, y, phase
        self._labels = None

    def resize(self, size):
        width, height = size
        self._canvas = pygame.Surface((max(2, width // 2), max(2, height // 2)))
        self._glow = pygame.Surface(self._canvas.get_size())
        self._scaled = pygame.Surface(size)
        self._bloom = pygame.Surface(size)
        canvas_w, canvas_h = self._canvas.get_size()
        self._center_x = canvas_w / 2
        self.horizon = canvas_h * 0.44
        self.focal = canvas_w * 0.5
        self._backdrop = vertical_gradient((canvas_w, canvas_h),
                                           [(205, 170, 222), (255, 196, 208), (255, 224, 198), (232, 200, 222)])
        if self._labels is None:
            font = pygame.font.SysFont(LABEL_FONTS, 40, bold=True)
            self._labels = [font.render(store, True, LABEL_INK) for store in STORES]

    # ------------------------------------------------------------- helpers
    def _project(self, x, y, z):
        return self._center_x + x * self.focal / z, self.horizon - y * self.focal / z

    @staticmethod
    def _fogged(color, z):
        return lerp_color(color, HAZE, clamp01(z / FAR) ** 0.8)

    def _quad(self, surf, color, corners):
        pygame.draw.polygon(surf, color, [self._project(*corner) for corner in corners])

    # ------------------------------------------------------------- draw
    def draw(self, surf, features, dt):
        now = features.time
        self._travel += dt * (0.35 + 1.1 * features.energy)
        canvas, glow = self._canvas, self._glow
        canvas.blit(self._backdrop, (0, 0))
        glow.fill((0, 0, 0))

        self._draw_shell(canvas)
        self._draw_floor(canvas)
        first_bay = int(self._travel)
        for bay_id in range(first_bay + int(FAR), first_bay - 1, -1):  # far to near
            self._draw_bay(canvas, glow, bay_id, features)
        first_prop = int(self._travel / PROP_SPACING)
        for prop_id in range(first_prop + int(FAR / PROP_SPACING) + 1, first_prop - 1, -1):
            self._draw_props(canvas, glow, prop_id, features, now)
        canvas.fill(AFTER_HOURS, special_flags=pygame.BLEND_RGB_MULT)  # the lights are half off
        self._draw_light_shafts(glow, features, now)
        self._draw_motes(glow, features, now)
        canvas.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # soften into a dream: upscale, ghost over the previous frame, then bloom
        pygame.transform.smoothscale(canvas, self.size, self._scaled)
        self._scaled.set_alpha(150)
        surf.blit(self._scaled, (0, 0))
        canvas_w, canvas_h = canvas.get_size()
        small = pygame.transform.smoothscale(canvas, (max(1, canvas_w // 6), max(1, canvas_h // 6)))
        pygame.transform.smoothscale(small, self.size, self._bloom)
        bloom_level = int(22 + 30 * features.bass + 25 * features.beat_pulse)
        self._bloom.fill((bloom_level, bloom_level, bloom_level), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(self._bloom, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_shell(self, canvas):
        self._quad(canvas, (226, 206, 240), [(-WALL_X, CEILING_Y, NEAR), (WALL_X, CEILING_Y, NEAR),
                                             (WALL_X, CEILING_Y, FAR), (-WALL_X, CEILING_Y, FAR)])
        self._quad(canvas, (255, 246, 250), [(-0.45, CEILING_Y, NEAR), (0.45, CEILING_Y, NEAR),
                                             (0.45, CEILING_Y, FAR), (-0.45, CEILING_Y, FAR)])
        self._quad(canvas, (246, 232, 226), [(-WALL_X, FLOOR_Y, NEAR), (WALL_X, FLOOR_Y, NEAR),
                                             (WALL_X, FLOOR_Y, FAR), (-WALL_X, FLOOR_Y, FAR)])
        for side in (-1, 1):
            wall_x = side * WALL_X
            self._quad(canvas, (240, 222, 218), [(wall_x, FLOOR_Y, NEAR), (wall_x, CEILING_Y, NEAR),
                                                 (wall_x, CEILING_Y, FAR), (wall_x, FLOOR_Y, FAR)])

    def _draw_floor(self, canvas):
        first_row = int((self._travel + NEAR) / TILE)
        for row_id in range(int((self._travel + FAR) / TILE), first_row - 1, -1):
            z_start = row_id * TILE - self._travel
            z_end = z_start + TILE
            if z_end <= NEAR:
                continue
            z_start = max(z_start, NEAR)
            color = self._fogged((242, 188, 212), z_start)
            for column in range(4):
                if (row_id + column) % 2:
                    x_left = -WALL_X + column * TILE
                    self._quad(canvas, color, [(x_left, FLOOR_Y, z_start), (x_left + TILE, FLOOR_Y, z_start),
                                               (x_left + TILE, FLOOR_Y, z_end), (x_left, FLOOR_Y, z_end)])

    def _draw_bay(self, canvas, glow, bay_id, features):
        z_start = bay_id - self._travel
        z_end = z_start + 1.0
        if z_end - 0.08 <= NEAR:
            return
        near_z = max(z_start + 0.08, NEAR)
        far_z = z_end - 0.08
        nb = len(features.bands)
        for side in (-1, 1):
            wall_x = side * WALL_X
            store = (bay_id * 7 + (3 if side > 0 else 0)) % len(STORES)
            color = STORE_COLORS[store % len(STORE_COLORS)]
            level = 0.55 + 0.45 * features.bands[(store * 5 + 3) % nb]
            if STORES[store].startswith("SALE") and features.beat_count % 2:
                level *= 0.45  # the sale sign blinks on the beat

            # shop windows, glowing with the store's colour
            shop = self._fogged(scale_color(lerp_color(color, (255, 255, 255), 0.45), 0.6 + 0.4 * level), near_z)
            self._quad(canvas, shop, [(wall_x, FLOOR_Y, near_z), (wall_x, 0.22, near_z),
                                      (wall_x, 0.22, far_z), (wall_x, FLOOR_Y, far_z)])
            upper = self._fogged(scale_color(lerp_color(color, (255, 255, 255), 0.6), 0.85), near_z)
            self._quad(canvas, upper, [(wall_x, 0.62, near_z), (wall_x, 1.02, near_z),
                                       (wall_x, 1.02, far_z), (wall_x, 0.62, far_z)])

            # mezzanine slab and railing
            slab = self._fogged((255, 250, 246), near_z)
            self._quad(canvas, slab, [(side * BALCONY_X, BALCONY_Y, near_z), (side * BALCONY_X, BALCONY_Y + 0.07, near_z),
                                      (side * BALCONY_X, BALCONY_Y + 0.07, far_z), (side * BALCONY_X, BALCONY_Y, far_z)])
            rail = self._fogged((150, 210, 205), near_z)
            pygame.draw.line(canvas, rail, self._project(side * BALCONY_X, BALCONY_Y + 0.3, near_z),
                             self._project(side * BALCONY_X, BALCONY_Y + 0.3, z_end))
            pygame.draw.line(canvas, rail, self._project(side * BALCONY_X, BALCONY_Y + 0.07, near_z),
                             self._project(side * BALCONY_X, BALCONY_Y + 0.3, near_z))

            # backlit sign hanging under the balcony, facing the walkway
            mid_z = (z_start + z_end) / 2
            if mid_z > NEAR + 0.2:
                self._draw_sign(canvas, glow, side, mid_z, store, color, level)

    def _draw_sign(self, canvas, glow, side, mid_z, store, color, level):
        scale = self.focal / mid_z
        sign_w, sign_h = 0.42 * scale, 0.11 * scale
        center = self._project(side * 0.6, 0.28, mid_z)
        rect = pygame.Rect(0, 0, int(sign_w), max(2, int(sign_h)))
        rect.center = (int(center[0]), int(center[1]))
        panel = self._fogged(scale_color(lerp_color(color, (255, 255, 255), 0.35), 0.75 + 0.25 * level), mid_z)
        canvas.fill(panel, rect)
        pygame.draw.rect(canvas, self._fogged((255, 255, 255), mid_z), rect, 1)
        label = self._labels[store]
        fit = min(rect.w * 0.9 / label.get_width(), rect.h * 0.75 / label.get_height())
        if label.get_height() * fit >= 4:
            text = pygame.transform.smoothscale(label, (max(1, int(label.get_width() * fit)),
                                                        max(1, int(label.get_height() * fit))))
            canvas.blit(text, text.get_rect(center=rect.center))
        # its light, plus a reflection in the polished floor
        glow.fill(scale_color(color, 0.14 * level), rect.inflate(rect.w // 3, rect.h))
        reflected = self._project(side * 0.6, 2 * FLOOR_Y - 0.28, mid_z)
        mirror = rect.copy()
        mirror.center = (int(reflected[0]), int(reflected[1]))
        glow.fill(scale_color(color, 0.16 * level), mirror)

    def _draw_props(self, canvas, glow, prop_id, features, now):
        z = prop_id * PROP_SPACING + 0.5 - self._travel
        if z <= NEAR + 0.15:
            return
        for side in (-1, 1):
            self._draw_palm(canvas, side * 0.45, z, prop_id * 2 + side, features, now)
        if prop_id % 3 == 0:
            self._draw_fountain(canvas, glow, z, features)

    def _draw_palm(self, canvas, x, z, palm_id, features, now):
        scale = self.focal / z
        planter = self._fogged((255, 214, 186), z)
        top_left = self._project(x - 0.11, FLOOR_Y + 0.18, z)
        canvas.fill(planter, (int(top_left[0]), int(top_left[1]), max(1, int(0.22 * scale)), max(1, int(0.18 * scale))))
        sway = math.sin(now * 0.8 + palm_id) * 0.05 + features.bass * 0.06
        trunk = [self._project(x + sway * step * step, FLOOR_Y + 0.18 + step * 0.75, z)
                 for step in (0.0, 0.25, 0.5, 0.75, 1.0)]
        line_width = max(1, int(0.025 * scale))
        pygame.draw.lines(canvas, self._fogged((176, 140, 120), z), False, trunk, line_width)
        crown_x, crown_y = trunk[-1]
        frond_color = self._fogged((92, 196, 168), z)
        for frond in range(7):
            angle = math.radians(20 + frond * (140 / 6)) + sway
            length = 0.32 * scale
            points = []
            for step in range(6):
                reach = step / 5
                points.append((crown_x + math.cos(angle) * length * reach,
                               crown_y - math.sin(angle) * length * reach + length * 0.55 * reach * reach))
            pygame.draw.lines(canvas, frond_color, False, points, line_width)

    def _draw_fountain(self, canvas, glow, z, features):
        scale = self.focal / z
        center = self._project(0.0, FLOOR_Y + 0.04, z)
        basin = pygame.Rect(0, 0, int(0.7 * scale), max(2, int(0.16 * scale)))
        basin.center = (int(center[0]), int(center[1]))
        pygame.draw.ellipse(canvas, self._fogged((196, 232, 238), z), basin)
        pygame.draw.ellipse(canvas, self._fogged((255, 255, 255), z), basin, 1)
        water = self._fogged((236, 252, 255), z)
        nb = len(features.bands)
        for jet in range(7):
            offset = (jet - 3) * 0.08
            height = 0.12 + 0.55 * features.bands[(jet * 4) % nb] + 0.15 * features.beat_pulse
            spread = offset * 0.8
            arc = []
            for step in range(10):
                progress = step / 9
                arc.append(self._project(offset + spread * progress,
                                         FLOOR_Y + 0.06 + 4 * height * progress * (1 - progress), z))
            pygame.draw.lines(canvas, water, False, arc, 1)
            pygame.draw.lines(glow, scale_color(SEAFOAM, 0.35), False, arc, 3)

    def _draw_light_shafts(self, glow, features, now):
        canvas_w, canvas_h = glow.get_size()
        for shaft in range(4):
            strength = (0.35 + 0.65 * features.energy) * (0.6 + 0.4 * math.sin(now * 0.3 + shaft * 1.7))
            color = scale_color((34, 26, 34), strength)
            left = canvas_w * (0.28 + shaft * 0.13)
            pygame.draw.polygon(glow, color, [(left, 0), (left + canvas_w * 0.05, 0),
                                              (left + canvas_w * 0.24, canvas_h), (left + canvas_w * 0.13, canvas_h)])

    def _draw_motes(self, glow, features, now):
        canvas_w, canvas_h = glow.get_size()
        for mote_x, mote_y, phase in self._motes.tolist():
            x = (mote_x + math.sin(now * 0.1 + phase * 6) * 0.02) * canvas_w
            y = ((mote_y - now * 0.01 * (0.5 + phase)) % 1.0) * canvas_h
            sparkle = 0.5 + 0.5 * math.sin(now * (1 + phase * 2) + phase * 30)
            brightness = int(60 + 150 * clamp01(features.treble * 1.5) * sparkle)
            glow.fill((brightness, brightness, brightness), (int(x), int(y), 1, 1))
