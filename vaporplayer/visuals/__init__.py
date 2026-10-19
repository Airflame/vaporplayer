"""Audio-reactive scenes and the engine that cycles and crossfades them."""
from __future__ import annotations

import pygame

from ..palette import NIGHT, smoothstep
from .dreampunk import Dreampunk
from .feedback import LiquidMemory
from .kaleido import Kaleidoscope
from .postfx import PostFX
from .sunset import SunsetGrid
from .tunnel import Tunnel

__all__ = ["VisualEngine", "PostFX"]


class VisualEngine:
    AUTO_INTERVAL = 40.0  # seconds before auto mode moves on (on the next beat)
    FADE_TIME = 1.4

    def __init__(self):
        self.scenes = [SunsetGrid(), Kaleidoscope(), Tunnel(), LiquidMemory(), Dreampunk()]
        self.index = 0
        self.auto = True
        self.on_switch = None
        self._since = 0.0
        self._prev = None
        self._fade = 0.0
        self._layers: dict[int, pygame.Surface] = {}  # each scene keeps its own persistent canvas

    @property
    def current(self):
        return self.scenes[self.index]

    def select(self, index: int):
        index %= len(self.scenes)
        if index == self.index:
            return
        self._prev, self._fade = self.index, 1.0
        self.index = index
        self._since = 0.0
        if self.on_switch:
            self.on_switch(self.current)

    def next(self):
        self.select(self.index + 1)

    def previous(self):
        self.select(self.index - 1)

    def _layer(self, scene_index: int, size) -> pygame.Surface:
        layer = self._layers.get(scene_index)
        if layer is None or layer.get_size() != size:
            layer = pygame.Surface(size)
            layer.fill(NIGHT)
            self._layers[scene_index] = layer
        return layer

    def render(self, screen: pygame.Surface, features, dt: float):
        size = screen.get_size()
        self._since += dt
        if self.auto and self._since > self.AUTO_INTERVAL and features.beat:
            self.next()

        layer = self._layer(self.index, size)
        self.current.render(layer, features, dt)
        screen.blit(layer, (0, 0))

        if self._prev is not None:
            self._fade -= dt / self.FADE_TIME
            if self._fade <= 0 or self._prev == self.index:
                self._prev = None
            else:
                old = self._layer(self._prev, size)
                self.scenes[self._prev].render(old, features, dt)
                old.set_alpha(int(255 * smoothstep(self._fade)))
                screen.blit(old, (0, 0))
                old.set_alpha(None)
