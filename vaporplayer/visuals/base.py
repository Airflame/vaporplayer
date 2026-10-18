from __future__ import annotations

import pygame

from ..audio import AudioFeatures


class Scene:
    name = "SCENE"
    tagline = ""  # Japanese subtitle shown on the title card

    def __init__(self):
        self.size = (0, 0)

    def resize(self, size):
        """Rebuild size-dependent resources."""

    def render(self, surf: pygame.Surface, f: AudioFeatures, dt: float):
        size = surf.get_size()
        if size != self.size:
            self.size = size
            self.resize(size)
        self.draw(surf, f, dt)

    def draw(self, surf: pygame.Surface, f: AudioFeatures, dt: float):
        raise NotImplementedError
