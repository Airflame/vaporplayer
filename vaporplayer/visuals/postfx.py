"""VHS / CRT post-processing: chromatic aberration, tracking glitches, noise,
vignette and scanlines."""
from __future__ import annotations

import random

import numpy as np
import pygame


class PostFX:
    def __init__(self):
        self.enabled = True
        self.size = None
        self._glitch = 0.0
        self._rng = random.Random()

    def _build(self, size):
        self.size = size
        w, h = size
        self._scanlines = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(0, h, 3):
            self._scanlines.fill((0, 0, 0, 55), (0, y, w, 1))

        x = np.linspace(-1, 1, w, dtype=np.float32)
        y = np.linspace(-1, 1, h, dtype=np.float32)
        d2 = x[:, None] ** 2 * 0.8 + y[None, :] ** 2
        v = (np.clip(1.15 - 0.45 * d2, 0.35, 1.0) * 255).astype(np.uint8)
        self._vignette = pygame.Surface(size)
        pygame.surfarray.blit_array(self._vignette, np.repeat(v[..., None], 3, axis=2))

        rng = np.random.default_rng()
        self._noise = []
        hw, hh = max(1, w // 2), max(1, h // 2)
        for _ in range(4):
            speck = (rng.random((hw, hh)) ** 8 * 60).astype(np.uint8)
            small = pygame.Surface((hw, hh))
            pygame.surfarray.blit_array(small, np.repeat(speck[..., None], 3, axis=2))
            self._noise.append(pygame.transform.scale(small, size))

    def apply(self, surf: pygame.Surface, f, dt: float):
        if not self.enabled:
            return
        if surf.get_size() != self.size:
            self._build(surf.get_size())
        w, h = self.size
        rng = self._rng

        # RGB split kicks in on beats
        shift = int(round(1 + 9 * f.beat_pulse ** 1.5))
        if shift >= 2:
            red = surf.copy()
            red.fill((255, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
            surf.fill((0, 255, 255), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(red, (shift, 0), special_flags=pygame.BLEND_RGB_ADD)

        # occasional VHS tracking tear on a hard beat
        if f.beat and rng.random() < 0.25:
            self._glitch = 0.18
        if self._glitch > 0:
            self._glitch -= dt
            for _ in range(3):
                y = rng.randrange(h)
                bh = min(rng.randint(4, max(5, h // 12)), h - y)
                strip = surf.subsurface((0, y, w, bh)).copy()
                surf.blit(strip, (rng.randint(-w // 20, w // 20), y))

        surf.blit(rng.choice(self._noise), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(self._vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(self._scanlines, (0, 0))
