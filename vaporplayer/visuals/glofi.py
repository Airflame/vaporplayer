"""Glo-fi: a faded summer memory on sun-bleached home video. A huge soft sun sinks into
the sea between two palms; light leaks, lens flare, reverb-like ghosting and a lifted,
washed-out grade turn it into chillwave haze, and the picture ducks on every kick like
a sidechained synth pad."""
from __future__ import annotations

import math

import pygame

from ..palette import clamp01, lerp_color, make_glow, scale_color, vertical_gradient
from .base import Scene

# (sky stops, sea stops, sand stops) for the calm blue hour and the peak golden hour
BLUE_HOUR = ([(62, 66, 128), (128, 92, 156), (206, 122, 150), (240, 170, 160)],
             [(130, 96, 150), (78, 66, 126), (52, 44, 100)],
             [(150, 108, 140), (112, 78, 116)])
GOLDEN_HOUR = ([(150, 92, 140), (226, 120, 118), (250, 160, 110), (255, 204, 140)],
               [(210, 128, 120), (150, 80, 112), (100, 50, 98)],
               [(214, 144, 136), (160, 98, 118)])
SUN_RINGS = [(255, 132, 120), (255, 160, 128), (255, 190, 140), (255, 216, 160), (255, 236, 196)]
SILHOUETTE = (34, 14, 44)
WASHED_GRADE = (255, 232, 218)       # a warm, faded print
GLINT = (255, 214, 150)
FOAM = (120, 96, 92)
LEAK_COLORS = [(255, 110, 40), (255, 60, 130), (255, 196, 80)]
FLARE_GHOSTS = [(0.45, 0.10, (70, 50, 40)), (0.85, 0.05, (40, 60, 70)), (1.15, 0.16, (50, 30, 60)),
                (1.5, 0.07, (70, 60, 30)), (1.9, 0.24, (30, 26, 40))]  # (distance, size, colour)
FROND_ANGLES = [-3.05, -2.55, -2.05, -1.55, -1.05, -0.55, -0.05]
# (trunk base x, crown x, crown y, sway phase, scale), as fractions of the canvas
PALMS = [(0.04, 0.12, 0.2, 0.0, 1.0), (0.98, 0.89, 0.3, 2.1, 0.85)]
REFLECTION_ROWS = 22
SWELLS = 6
GHOSTING = 130   # how much of each new frame replaces the last: lower means longer reverb trails
LEAK_DECAY = 1.1


class GloFi(Scene):
    name = "GLO-FI"
    tagline = "夏の思い出"

    def __init__(self):
        super().__init__()
        self._swell = 0.0
        self._wash = 0.0
        self._leak_flares = [0.0] * len(LEAK_COLORS)

    def resize(self, size):
        width, height = size
        self._canvas = pygame.Surface((max(2, width // 2), max(2, height // 2)))
        canvas_w, canvas_h = self._canvas.get_size()
        self._glow = pygame.Surface((canvas_w, canvas_h))
        self._atmosphere = pygame.Surface((max(2, canvas_w // 4), max(2, canvas_h // 4)))
        self._atmosphere_scaled = pygame.Surface((canvas_w, canvas_h))
        self._scaled = pygame.Surface(size)
        self._bloom = pygame.Surface(size)

        self._horizon = int(canvas_h * 0.56)
        self._shore = int(canvas_h * 0.86)
        self._blue_hour = self._paint_backdrop(BLUE_HOUR)
        self._golden_hour = self._paint_backdrop(GOLDEN_HOUR)

        atmosphere_w, atmosphere_h = self._atmosphere.get_size()
        self._sun_halo = make_glow(atmosphere_h * 1.2, (255, 130, 80), falloff=2.4)
        self._horizon_haze = vertical_gradient((atmosphere_w, atmosphere_h // 3),
                                               [(0, 0, 0), (60, 36, 30), (0, 0, 0)])
        self._leaks = [make_glow(atmosphere_h * 1.4, color, falloff=1.3) for color in LEAK_COLORS]
        self._ghosts = [make_glow(canvas_h * ghost_size, color, falloff=0.5)
                        for _, ghost_size, color in FLARE_GHOSTS]

    def _paint_backdrop(self, stops):
        sky_stops, sea_stops, sand_stops = stops
        canvas_w, canvas_h = self._canvas.get_size()
        backdrop = pygame.Surface((canvas_w, canvas_h))
        backdrop.blit(vertical_gradient((canvas_w, self._horizon), sky_stops), (0, 0))
        backdrop.blit(vertical_gradient((canvas_w, self._shore - self._horizon), sea_stops), (0, self._horizon))
        backdrop.blit(vertical_gradient((canvas_w, canvas_h - self._shore), sand_stops), (0, self._shore))
        return backdrop

    @staticmethod
    def _dimmed(source, brightness):
        """A copy of an additive glow surface at the given brightness."""
        level = int(255 * clamp01(brightness))
        dimmed = source.copy()
        dimmed.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
        return dimmed

    # ------------------------------------------------------------------ draw
    def draw(self, surf, features, dt):
        now = features.time
        self._swell = (self._swell + dt * (0.05 + 0.2 * features.energy)) % 1.0
        self._wash += (features.bass - self._wash) * min(1.0, dt * 3)
        if features.beat and features.beat_count % 4 == 0:
            self._leak_flares[features.beat_count // 4 % len(LEAK_COLORS)] = 1.0
        self._leak_flares = [max(0.0, flare - dt * LEAK_DECAY) for flare in self._leak_flares]

        canvas, glow = self._canvas, self._glow
        canvas_w, canvas_h = canvas.get_size()
        mood = clamp01(features.intensity * 1.4)
        canvas.blit(self._blue_hour, (0, 0))
        self._golden_hour.set_alpha(int(255 * mood))
        canvas.blit(self._golden_hour, (0, 0))
        glow.fill((0, 0, 0))

        sun_x = canvas_w * (0.6 + 0.03 * math.sin(now * 0.05))
        sun_radius = canvas_h * 0.17 * (1 + 0.06 * features.bass + 0.03 * features.beat_pulse)
        sun_y = self._horizon - sun_radius * 0.45
        self._draw_sun(canvas, sun_x, sun_y, sun_radius)
        self._draw_swells(glow, features, now)
        self._draw_reflection(glow, features, now, sun_x, sun_radius)
        self._draw_shoreline(canvas, glow, now)
        self._draw_flare(glow, features, sun_x, sun_y)
        for palm in PALMS:
            self._draw_palm(canvas, palm, features, now)
        canvas.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        self._draw_atmosphere(features, now, sun_x, sun_y)
        pygame.transform.smoothscale(self._atmosphere, (canvas_w, canvas_h), self._atmosphere_scaled)
        canvas.blit(self._atmosphere_scaled, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # the washed-out grade: warm the print, lift the blacks, overexpose with energy
        canvas.fill(WASHED_GRADE, special_flags=pygame.BLEND_RGB_MULT)
        exposure = features.energy
        canvas.fill((int(26 + 20 * exposure), int(14 + 10 * exposure), int(30 + 14 * exposure)),
                    special_flags=pygame.BLEND_RGB_ADD)
        # sidechain: the whole picture ducks on the kick and swells back
        duck = 1 - 0.18 * features.beat_pulse
        duck_level = int(255 * duck)
        canvas.fill((duck_level, duck_level, duck_level), special_flags=pygame.BLEND_RGB_MULT)

        # reverb for the eyes: ghost over the previous frame, then a heavy bloom
        pygame.transform.smoothscale(canvas, self.size, self._scaled)
        self._scaled.set_alpha(GHOSTING)
        surf.blit(self._scaled, (0, 0))
        small = pygame.transform.smoothscale(canvas, (max(1, canvas_w // 8), max(1, canvas_h // 8)))
        pygame.transform.smoothscale(small, self.size, self._bloom)
        bloom_level = int((24 + 22 * features.energy) * duck)
        self._bloom.fill((bloom_level, bloom_level, bloom_level), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(self._bloom, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_sun(self, canvas, sun_x, sun_y, sun_radius):
        canvas.set_clip(pygame.Rect(0, 0, canvas.get_width(), self._horizon))
        for ring, color in enumerate(SUN_RINGS):
            pygame.draw.circle(canvas, color, (sun_x, sun_y), sun_radius * (1 - ring * 0.16))
        canvas.set_clip(None)

    def _draw_swells(self, glow, features, now):
        """Soft lines of swell rolling in towards the beach, faster with energy."""
        canvas_w = glow.get_width()
        sea_depth = self._shore - self._horizon
        for swell in range(SWELLS):
            progress = (self._swell + swell / SWELLS) % 1.0
            y = self._horizon + sea_depth * progress ** 1.8
            brightness = math.sin(math.pi * progress) * (8 + 18 * features.mid)
            color = scale_color((255, 200, 220), brightness / 255)
            points = [(x, y + math.sin(x * 0.02 + now * 0.8 + swell) * (1 + progress * 3))
                      for x in range(0, canvas_w + 16, 16)]
            pygame.draw.lines(glow, color, False, points, 1 + int(progress * 2))

    def _draw_reflection(self, glow, features, now, sun_x, sun_radius):
        """The sun's glitter path: each row of glints is a band, treble at the horizon, bass up close."""
        bands = features.bands
        band_total = len(bands)
        sea_depth = self._shore - self._horizon
        pygame.draw.line(glow, scale_color(GLINT, 0.3), (0, self._horizon), (glow.get_width(), self._horizon))
        for row in range(REFLECTION_ROWS):
            nearness = (row + 0.5) / REFLECTION_ROWS
            y = self._horizon + 2 + (sea_depth - 4) * nearness ** 1.4
            level = float(bands[int((1 - nearness) * (band_total - 1))])
            half_width = sun_radius * (0.3 + 0.9 * nearness) * (0.4 + 1.2 * level)
            thickness = max(1, int(1 + nearness * 3))
            for dash in range(3):
                shimmer = 0.7 + 0.3 * math.sin(now * 7 + row * 3 + dash * 5)
                center = sun_x + math.sin(now * 1.6 + row * 1.7 + dash * 2.1) * half_width * 0.55
                reach = half_width * 0.4
                color = scale_color(GLINT, (0.25 + 0.75 * level) * shimmer)
                pygame.draw.line(glow, color, (center - reach, y), (center + reach, y), thickness)

    def _draw_shoreline(self, canvas, glow, now):
        """Water washes up the sand and draws back with the bass."""
        canvas_w, canvas_h = canvas.get_size()
        beach_depth = canvas_h - self._shore
        reach = (0.15 + 0.6 * clamp01(self._wash * 1.3)) * beach_depth
        edge = [(x, self._shore + reach + math.sin(x * 0.025 + now * 0.9) * beach_depth * 0.08)
                for x in range(0, canvas_w + 12, 12)]
        wet = lerp_color(BLUE_HOUR[1][-1], GOLDEN_HOUR[1][-1], 0.5)
        pygame.draw.polygon(canvas, wet, [(0, self._shore)] + edge + [(canvas_w, self._shore)])
        pygame.draw.lines(glow, FOAM, False, edge, 2)

    def _draw_flare(self, glow, features, sun_x, sun_y):
        """Lens-flare ghosts strung along the line from the sun through the middle of the frame."""
        canvas_w, canvas_h = glow.get_size()
        middle_x, middle_y = canvas_w / 2, canvas_h / 2
        strength = 0.3 + 0.4 * features.energy + 0.3 * features.beat_pulse
        for ghost, (distance, _, _) in zip(self._ghosts, FLARE_GHOSTS):
            x = sun_x + (middle_x - sun_x) * distance * 2
            y = sun_y + (middle_y - sun_y) * distance * 2
            dimmed = self._dimmed(ghost, strength)
            glow.blit(dimmed, dimmed.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_palm(self, canvas, palm, features, now):
        base_x, crown_x, crown_y, phase, scale = palm
        canvas_w, canvas_h = canvas.get_size()
        sway = (math.sin(now * 0.5 + phase) * 0.04 + math.sin(now * 1.3 + phase * 2) * 0.015
                + features.mid * 0.05)
        base = (base_x * canvas_w, canvas_h + 4)
        crown = (crown_x * canvas_w + sway * canvas_h * 0.4, crown_y * canvas_h)
        bend = (base[0], (base[1] + crown[1]) / 2)
        trunk = []
        for step in range(15):
            along = step / 14
            trunk.append(((1 - along) ** 2 * base[0] + 2 * (1 - along) * along * bend[0] + along ** 2 * crown[0],
                          (1 - along) ** 2 * base[1] + 2 * (1 - along) * along * bend[1] + along ** 2 * crown[1]))
        for step in range(14):
            thickness = int(canvas_h * scale * (0.034 - 0.016 * step / 14))
            pygame.draw.line(canvas, SILHOUETTE, trunk[step], trunk[step + 1], max(2, thickness))
            pygame.draw.circle(canvas, SILHOUETTE, trunk[step + 1], max(1, thickness // 2))

        flutter_strength = 0.03 + 0.05 * features.treble
        for frond, base_angle in enumerate(FROND_ANGLES):
            angle = base_angle + sway * 1.5 + math.sin(now * 1.7 + frond * 1.3 + phase) * flutter_strength
            length = canvas_h * 0.26 * scale * (0.8 + 0.2 * math.cos(frond * 1.3))
            spine = [(crown[0] + math.cos(angle) * length * along,
                      crown[1] + math.sin(angle) * length * along + 0.6 * length * along * along)
                     for along in (step / 10 for step in range(11))]
            upper, lower = [], []
            for step in range(len(spine)):
                ahead = spine[min(step + 1, len(spine) - 1)]
                behind = spine[max(step - 1, 0)]
                direction_x, direction_y = ahead[0] - behind[0], ahead[1] - behind[1]
                norm = math.hypot(direction_x, direction_y) or 1.0
                normal_x, normal_y = -direction_y / norm, direction_x / norm
                width = length * 0.09 * math.sin(math.pi * step / 10) ** 0.7 * (1.0 if step % 2 else 0.55)
                upper.append((spine[step][0] + normal_x * width, spine[step][1] + normal_y * width))
                lower.append((spine[step][0] - normal_x * width, spine[step][1] - normal_y * width))
            pygame.draw.polygon(canvas, SILHOUETTE, upper + lower[::-1])
        pygame.draw.circle(canvas, SILHOUETTE, crown, canvas_h * scale * 0.022)

    def _draw_atmosphere(self, features, now, sun_x, sun_y):
        """Low-resolution light: the sun's halo, haze on the horizon and film light leaks."""
        atmosphere = self._atmosphere
        atmosphere.fill((0, 0, 0))
        atmosphere_w, atmosphere_h = atmosphere.get_size()
        to_atmosphere = atmosphere_w / self._canvas.get_width()

        haze = self._dimmed(self._horizon_haze, 0.6 + 0.4 * features.intensity)
        atmosphere.blit(haze, haze.get_rect(center=(atmosphere_w // 2, int(self._horizon * to_atmosphere))),
                        special_flags=pygame.BLEND_RGB_ADD)
        halo = self._dimmed(self._sun_halo, 0.3 + 0.15 * features.bass + 0.1 * features.beat_pulse)
        atmosphere.blit(halo, halo.get_rect(center=(int(sun_x * to_atmosphere), int(sun_y * to_atmosphere))),
                        special_flags=pygame.BLEND_RGB_ADD)

        anchors = [(-0.08, 0.35 + 0.25 * math.sin(now * 0.07)),          # drifting down the left edge
                   (0.85 + 0.15 * math.sin(now * 0.05 + 1), -0.12),       # along the top
                   (1.08, 0.7 + 0.2 * math.sin(now * 0.06 + 2))]          # up the right edge
        for leak, (anchor_x, anchor_y), flare in zip(self._leaks, anchors, self._leak_flares):
            brightness = 0.12 + 0.2 * features.intensity + 0.6 * flare
            dimmed = self._dimmed(leak, brightness)
            center = (int(anchor_x * atmosphere_w), int(anchor_y * atmosphere_h))
            atmosphere.blit(dimmed, dimmed.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)
