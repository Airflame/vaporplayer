"""Retro-OS styled interface drawn over the visualiser."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from .palette import CYAN, MINT, PINK, YELLOW, clamp01, fullwidth, horizontal_gradient, lerp_color

HELP_LINES = [
    ("SPACE", "play / pause"),
    ("LEFT / RIGHT", "seek 5 s  (+SHIFT: 30 s)"),
    ("UP / DOWN", "volume"),
    ("N / P", "next / previous track"),
    ("S", "stop"),
    ("V / TAB", "next visual  (+SHIFT: previous)"),
    ("1 - 7", "pick a visual"),
    ("A", "auto-cycle visuals on beats"),
    ("O / SHIFT+O", "open files / open folder"),
    ("L", "playlist"),
    ("DELETE", "remove current track from playlist"),
    ("F / F11", "fullscreen"),
    ("H", "hide interface"),
    ("X", "VHS effects on / off"),
    ("F1", "this help"),
]

BODY = (24, 8, 48, 215)
LIGHT = (255, 255, 255, 150)
SHADOW = (0, 0, 0, 200)
LCD_BG = (4, 12, 10, 235)


@dataclass
class Fonts:
    ui: pygame.font.Font
    bold: pygame.font.Font
    small: pygame.font.Font
    lcd: pygame.font.Font
    big: pygame.font.Font
    jp: pygame.font.Font | None
    caption: pygame.font.Font  # title bars; fullwidth-capable when `wide`
    wide: bool  # whether `big` and `caption` can render fullwidth Ｌａｔｉｎ


def _supports(font: pygame.font.Font, text: str) -> bool:
    return all(glyph_metrics is not None for glyph_metrics in font.metrics(text))


def load_fonts() -> Fonts:
    mono = "consolas,lucidaconsole,couriernew,dejavusansmono"
    cjk = "msgothic,yugothic,meiryo,notosanscjkjp,notosansjp,ipagothic,takaogothic"
    big = pygame.font.SysFont(cjk, 46)
    wide = _supports(big, "ＶＡＰＯＲ")
    if not wide:
        big = pygame.font.SysFont("arialblack,impact,arial", 42, bold=True)
    jp = pygame.font.SysFont(cjk, 20)
    bold = pygame.font.SysFont(mono, 14, bold=True)
    return Fonts(
        ui=pygame.font.SysFont(mono, 14),
        bold=bold,
        small=pygame.font.SysFont(mono, 12),
        lcd=pygame.font.SysFont(mono, 19, bold=True),
        big=big,
        jp=jp if _supports(jp, "夢の電脳") else None,
        caption=pygame.font.SysFont(cjk, 14, bold=True) if wide else bold,
        wide=wide,
    )


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def bevel(surf, rect, raised=True):
    box = pygame.Rect(rect)
    tl, br = (LIGHT, SHADOW) if raised else (SHADOW, LIGHT)
    pygame.draw.line(surf, tl, box.topleft, (box.right - 1, box.top))
    pygame.draw.line(surf, tl, box.topleft, (box.left, box.bottom - 1))
    pygame.draw.line(surf, br, (box.left, box.bottom - 1), (box.right - 1, box.bottom - 1))
    pygame.draw.line(surf, br, (box.right - 1, box.top), (box.right - 1, box.bottom - 1))


def draw_icon(surf, kind: str, rect, color):
    cx, cy = rect.center
    half = 7
    if kind == "play":
        pygame.draw.polygon(surf, color, [(cx - half + 2, cy - half), (cx - half + 2, cy + half), (cx + half, cy)])
    elif kind == "pause":
        pygame.draw.rect(surf, color, (cx - 6, cy - half, 4, 2 * half))
        pygame.draw.rect(surf, color, (cx + 2, cy - half, 4, 2 * half))
    elif kind == "stop":
        pygame.draw.rect(surf, color, (cx - half + 1, cy - half + 1, 2 * half - 2, 2 * half - 2))
    elif kind == "prev":
        pygame.draw.rect(surf, color, (cx - half, cy - half, 3, 2 * half))
        pygame.draw.polygon(surf, color, [(cx + half, cy - half), (cx + half, cy + half), (cx - half + 3, cy)])
    elif kind == "next":
        pygame.draw.rect(surf, color, (cx + half - 3, cy - half, 3, 2 * half))
        pygame.draw.polygon(surf, color, [(cx - half, cy - half), (cx - half, cy + half), (cx + half - 3, cy)])


class Button:
    def __init__(self, action: str, icon: str | None = None, label: str | None = None, width: int = 38):
        self.action = action
        self.icon = icon
        self.label = label
        self.width = width
        self.rect = pygame.Rect(0, 0, width, 28)

    def draw(self, surf, fonts: Fonts, hovered: bool, pressed: bool, active: bool, icon: str | None):
        face = (95, 40, 145, 235) if hovered else (60, 22, 100, 235)
        surf.fill(face, self.rect)
        bevel(surf, self.rect, raised=not pressed)
        color = MINT if active else (240, 225, 255)
        inner = self.rect.move(1, 1) if pressed else self.rect
        if icon:
            draw_icon(surf, icon, inner, color)
        else:
            img = fonts.bold.render(self.label, True, color)
            surf.blit(img, img.get_rect(center=inner.center))


class UI:
    WIN_W, WIN_H = 500, 196

    def __init__(self, player, visuals, actions: dict):
        self.player = player
        self.visuals = visuals
        self.actions = actions  # name -> callable, supplied by the app
        self.fonts = load_fonts()
        self.overlay = None
        self.visible = True
        self.show_playlist = False
        self.show_help = False
        self.fullscreen = False
        self._idle = 0.0
        self._alpha = 255.0
        self._mouse = (0, 0)
        self._pressed: Button | None = None
        self._drag_seek = False
        self._seek_preview = 0.0
        self._drag_vol = False
        self._marquee = 0.0
        self._list_scroll = 0
        self._title_scene = None
        self._title_timer = 0.0
        self._toast = ""
        self._toast_timer = 0.0
        self._grad_cache: dict = {}
        self._title_cache = ("", None)
        # draggable windows: offset from each one's default anchor, and stacking order (last = top)
        self._offsets = {"idle": (0, 0), "main": (0, 0), "list": (0, 0)}
        self._defaults: dict[str, pygame.Rect] = {}
        self._window_order = ["idle", "main", "list"]
        self._drag_win: tuple[str, int, int] | None = None  # (window, grab x, grab y)
        self._size = (1280, 720)
        self.buttons = [
            Button("prev", icon="prev"), Button("play", icon="play"), Button("next", icon="next"),
            Button("stop", icon="stop"),
            Button("open", label="OPEN", width=54), Button("list", label="LIST", width=54),
            Button("vis", label="VIS", width=54), Button("auto", label="AUTO", width=54),
        ]
        visuals.on_switch = self.announce_scene
        self.layout((1280, 720))

    # ------------------------------------------------------------------ public
    def announce_scene(self, scene):
        self._title_scene = scene
        self._title_timer = 3.0

    def toast(self, text: str):
        self._toast = text
        self._toast_timer = 2.5

    def toggle_playlist(self):
        self.show_playlist = not self.show_playlist
        if self.show_playlist:
            self._list_scroll = max(0, self.player.index - 3)
            self._raise("list")

    @property
    def interactive(self) -> bool:
        return self.visible and self._alpha > 40

    # ------------------------------------------------------------------ layout
    def layout(self, size):
        self._size = size
        width, height = size
        screen = pygame.Rect(0, 0, width, height)
        self.win = self._place("main", pygame.Rect(16, height - self.WIN_H - 16, self.WIN_W, self.WIN_H), screen)
        x, y = self.win.topleft
        self.close_btn = pygame.Rect(self.win.right - 21, y + 6, 16, 14)
        self.min_btn = pygame.Rect(self.win.right - 39, y + 6, 16, 14)
        self.lcd = pygame.Rect(x + 10, y + 32, self.WIN_W - 20, 62)
        self.progress = pygame.Rect(x + 10, self.lcd.bottom + 10, self.WIN_W - 20, 14)
        bx, by = x + 10, self.progress.bottom + 10
        for i, button in enumerate(self.buttons):
            if i == 4:
                bx += 12
            button.rect = pygame.Rect(bx, by, button.width, 28)
            bx += button.width + 4
        self.vol_rect = pygame.Rect(x + 52, by + 28 + 15, 160, 10)

        rows = max(3, min(len(self.player.playlist), (height - self.WIN_H - 120) // 20))
        self.list_win = self._place("list", pygame.Rect(width - 376, 16, 360, 36 + rows * 20), screen)
        self.list_rows = rows

        idle = pygame.Rect(0, 0, 520, 190)
        idle.center = (width // 2, int(height * 0.42))
        self.idle_win = self._place("idle", idle, screen)

    def _place(self, name: str, default: pygame.Rect, screen: pygame.Rect) -> pygame.Rect:
        """Apply the window's drag offset to its default rect, keeping it on screen."""
        self._defaults[name] = default
        rect = default.move(self._offsets[name]).clamp(screen)
        self._offsets[name] = (rect.x - default.x, rect.y - default.y)
        return rect

    def _window_rect(self, name: str) -> pygame.Rect:
        return {"idle": self.idle_win, "main": self.win, "list": self.list_win}[name]

    def _window_shown(self, name: str) -> bool:
        if name == "idle":
            return not self.player.playlist
        if name == "list":
            return self.show_playlist
        return True

    def _window_at(self, pos) -> str | None:
        """The topmost visible window under `pos`."""
        for name in reversed(self._window_order):
            if self._window_shown(name) and self._window_rect(name).collidepoint(pos):
                return name
        return None

    def _raise(self, name: str):
        self._window_order.remove(name)
        self._window_order.append(name)

    @staticmethod
    def _title_bar(rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, 20)

    # ------------------------------------------------------------------ events
    def handle_event(self, ev) -> bool:
        """Return True when the interface consumed the event."""
        if ev.type == pygame.MOUSEMOTION:
            self._idle = 0.0
            self._mouse = ev.pos
            if self._drag_win:
                name, gx, gy = self._drag_win
                default = self._defaults[name]
                self._offsets[name] = (ev.pos[0] - gx - default.x, ev.pos[1] - gy - default.y)
                self.layout(self._size)
                return True
            if self._drag_vol:
                self._set_volume_from(ev.pos[0])
            elif self._drag_seek:
                self._seek_preview = self._frac(self.progress, ev.pos[0])
            return self._drag_vol or self._drag_seek
        if ev.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
            return False
        self._idle = 0.0
        if not self.interactive:
            return False

        if ev.type == pygame.MOUSEWHEEL:
            hit = self._window_at(self._mouse)
            if hit == "list":
                self._scroll_list(-ev.y * 2)
            elif hit == "main":
                self.player.set_volume(self.player.volume + ev.y * 0.05)
            return hit is not None

        if ev.button != 1:
            return False
        pos = ev.pos
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if self.show_help:
                self.show_help = False
                return True
            hit = self._window_at(pos)
            if hit is None:
                return False
            self._raise(hit)
            rect = self._window_rect(hit)
            on_caption_button = hit == "main" and (self.close_btn.collidepoint(pos) or self.min_btn.collidepoint(pos))
            if self._title_bar(rect).collidepoint(pos) and not on_caption_button:
                self._drag_win = (hit, pos[0] - rect.x, pos[1] - rect.y)
                return True
            if hit == "list":
                row = (pos[1] - self.list_win.y - 30) // 20
                if 0 <= row < self.list_rows:
                    track_index = self._list_scroll + row
                    if track_index < len(self.player.playlist):
                        self.player.play_index(track_index)
                return True
            if hit == "idle":
                return True
            if self.close_btn.collidepoint(pos):
                self.actions["quit"]()
                return True
            if self.min_btn.collidepoint(pos):
                self.visible = False
                self.toast("H  brings the interface back")
                return True
            for button in self.buttons:
                if button.rect.collidepoint(pos):
                    self._pressed = button
                    return True
            if self.progress.inflate(0, 8).collidepoint(pos) and self.player.current:
                self._drag_seek = True
                self._seek_preview = self._frac(self.progress, pos[0])
                return True
            if self.vol_rect.inflate(8, 12).collidepoint(pos):
                self._drag_vol = True
                self._set_volume_from(pos[0])
                return True
            return True

        # MOUSEBUTTONUP
        consumed = False
        if self._drag_win is not None:
            self._drag_win = None
            consumed = True
        if self._pressed is not None:
            if self._pressed.rect.collidepoint(pos):
                self._fire(self._pressed.action)
            self._pressed = None
            consumed = True
        if self._drag_seek:
            self.player.seek(self._seek_preview * self.player.duration)
            self._drag_seek = False
            consumed = True
        if self._drag_vol:
            self._drag_vol = False
            consumed = True
        return consumed

    def _fire(self, action: str):
        player, visuals = self.player, self.visuals
        {
            "prev": player.previous, "play": player.toggle_pause, "next": player.next, "stop": player.stop,
            "open": self.actions["open"], "list": self.toggle_playlist, "vis": visuals.next,
            "auto": self.actions["auto"],
        }[action]()

    @staticmethod
    def _frac(rect, x) -> float:
        return clamp01((x - rect.x) / max(1, rect.w))

    def _set_volume_from(self, x):
        self.player.set_volume(self._frac(self.vol_rect, x))

    def _scroll_list(self, delta):
        self._list_scroll = max(0, min(self._list_scroll + delta, len(self.player.playlist) - self.list_rows))

    # ----------------------------------------------------------------- drawing
    def _gradient(self, size, stops):
        key = (size, tuple(stops))
        if key not in self._grad_cache:
            self._grad_cache[key] = horizontal_gradient(size, stops)
        return self._grad_cache[key]

    def _window(self, surf, rect, title):
        surf.fill(BODY, rect)
        bevel(surf, rect)
        bar = self._title_bar(rect)
        surf.blit(self._gradient(bar.size, [PINK, (185, 103, 255), CYAN]), bar)
        font = self.fonts.caption
        surf.blit(font.render(title, True, (40, 0, 60)), (bar.x + 7, bar.y + 3))
        surf.blit(font.render(title, True, (255, 255, 255)), (bar.x + 6, bar.y + 2))

    def _caption_buttons(self, surf):
        for box, glyph in ((self.min_btn, "min"), (self.close_btn, "close")):
            surf.fill((200, 190, 225, 255), box)
            bevel(surf, box)
            glyph_color = (30, 10, 50)
            if glyph == "min":
                pygame.draw.line(surf, glyph_color, (box.x + 4, box.bottom - 4), (box.right - 5, box.bottom - 4), 2)
            else:
                pygame.draw.line(surf, glyph_color, (box.x + 4, box.y + 3), (box.right - 5, box.bottom - 4), 2)
                pygame.draw.line(surf, glyph_color, (box.x + 4, box.bottom - 4), (box.right - 5, box.y + 3), 2)

    def _update_visibility(self, dt):
        self._idle += dt
        hovering = self._window_at(self._mouse) is not None
        wanted = (not self.player.playlist or self.show_help or self._drag_seek or self._drag_vol
                  or self._drag_win is not None or hovering or self._idle < 3.0 or not self.player.playing)
        target = 255.0 if (self.visible and wanted) else 0.0
        self._alpha += (target - self._alpha) * (1.0 - math.exp(-dt * (10.0 if target else 3.0)))
        pygame.mouse.set_visible(self._idle < 3.0 or self._alpha > 10 or not self.fullscreen)

    def draw(self, screen, features, dt):
        size = screen.get_size()
        if self.overlay is None or self.overlay.get_size() != size:
            self.overlay = pygame.Surface(size, pygame.SRCALPHA)
        self.layout(size)
        self._update_visibility(dt)
        self._marquee += dt

        self._draw_title_card(screen, dt)
        self._draw_toast(screen, dt)
        if self._alpha <= 1:
            return
        ov = self.overlay
        ov.fill((0, 0, 0, 0))
        for name in self._window_order:
            if not self._window_shown(name):
                continue
            if name == "idle":
                self._draw_idle(ov)
            elif name == "main":
                self._draw_main(ov, features)
            else:
                self._draw_playlist(ov)
        if self.show_help:
            self._draw_help(ov)
        ov.set_alpha(int(self._alpha))
        screen.blit(ov, (0, 0))

    def _draw_main(self, surf, features):
        player, fonts = self.player, self.fonts
        self._window(surf, self.win, fullwidth("VAPORPLAYER.EXE") if fonts.wide else "VAPORPLAYER.EXE")
        self._caption_buttons(surf)

        # LCD: title marquee, status line and a little LED spectrum
        lcd = self.lcd
        surf.fill(LCD_BG, lcd)
        bevel(surf, lcd, raised=False)
        spec_w = 132
        text_area = pygame.Rect(lcd.x + 8, lcd.y + 6, lcd.w - spec_w - 22, 24)
        if player.current:
            title = player.current.track.title
        elif player.loading:
            title = "loading " + player.playlist[player.index].title + " ..."
        else:
            title = "no disk inserted"
        if self._title_cache[0] != title:
            self._title_cache = (title, fonts.lcd.render(title, True, MINT))
        img = self._title_cache[1]
        surf.set_clip(text_area)
        if img.get_width() > text_area.w:
            gap = 60
            off = int(self._marquee * 40) % (img.get_width() + gap)
            surf.blit(img, (text_area.x - off, text_area.y))
            surf.blit(img, (text_area.x - off + img.get_width() + gap, text_area.y))
        else:
            surf.blit(img, text_area.topleft)
        surf.set_clip(None)

        if player.status and not player.current:
            line, col = player.status, PINK
        else:
            state = "LOAD" if player.loading else "PLAY" if player.playing else "PAUSE" if player.current else "IDLE"
            pos = self._seek_preview * player.duration if self._drag_seek else player.position
            track_count = len(player.playlist)
            line = f"{state:<5}  {fmt_time(pos)} / {fmt_time(player.duration)}   [{player.index + 1:02d}/{track_count:02d}]" if track_count else state
            col = (120, 255, 200)
        surf.set_clip(pygame.Rect(lcd.x + 8, lcd.y + 34, text_area.w, 20))
        surf.blit(fonts.ui.render(line, True, col), (lcd.x + 8, lcd.y + 36))
        surf.set_clip(None)

        bars = 22
        sx = lcd.right - spec_w - 8
        bw = spec_w / bars
        nb = len(features.bands)
        for i in range(bars):
            level = features.bands[int(i * nb / bars)]
            segs = int(level * 10 + 0.5)
            for s in range(segs):
                led_color = lerp_color(MINT, PINK, s / 9) + (255,)
                surf.fill(led_color, (int(sx + i * bw), lcd.bottom - 8 - s * 5, max(1, int(bw) - 1), 4))

        # progress bar
        pr = self.progress
        surf.fill((10, 2, 20, 230), pr)
        bevel(surf, pr, raised=False)
        frac = self._seek_preview if self._drag_seek else (player.position / player.duration if player.duration else 0)
        fill_w = int((pr.w - 4) * clamp01(frac))
        if fill_w > 0:
            grad = self._gradient((pr.w - 4, pr.h - 4), [PINK, (185, 103, 255), CYAN])
            surf.blit(grad, (pr.x + 2, pr.y + 2), (0, 0, fill_w, pr.h - 4))
            pygame.draw.rect(surf, (255, 255, 255), (pr.x + 2 + fill_w - 2, pr.y + 1, 3, pr.h - 2))

        # transport + function buttons
        for button in self.buttons:
            icon = button.icon
            if button.action == "play" and player.playing:
                icon = "pause"
            active = (button.action == "auto" and self.visuals.auto) or (button.action == "list" and self.show_playlist)
            button.draw(surf, fonts, button.rect.collidepoint(self._mouse), button is self._pressed, active, icon)

        # volume + current scene
        vr = self.vol_rect
        surf.blit(fonts.bold.render("VOL", True, (240, 225, 255)), (self.win.x + 12, vr.y - 3))
        surf.fill((10, 2, 20, 230), vr)
        bevel(surf, vr, raised=False)
        vw = int((vr.w - 4) * player.volume)
        if vw > 0:
            surf.blit(self._gradient((vr.w - 4, vr.h - 4), [MINT, YELLOW, PINK]), (vr.x + 2, vr.y + 2),
                      (0, 0, vw, vr.h - 4))
        knob = pygame.Rect(0, 0, 8, 16)
        knob.center = (vr.x + 2 + vw, vr.centery)
        surf.fill((200, 190, 225, 255), knob)
        bevel(surf, knob)
        scene = self.visuals.current
        label = f"VIS {self.visuals.index + 1}: {scene.name}"
        img = fonts.small.render(label, True, CYAN)
        surf.blit(img, img.get_rect(midright=(self.win.right - 12, vr.centery)))

    def _draw_playlist(self, surf):
        player, fonts = self.player, self.fonts
        window_rect = self.list_win
        self._window(surf, window_rect, "PLAYLIST.TXT")
        inner = pygame.Rect(window_rect.x + 6, window_rect.y + 28, window_rect.w - 12, window_rect.h - 34)
        surf.fill(LCD_BG, inner)
        bevel(surf, inner, raised=False)
        if not player.playlist:
            surf.blit(fonts.ui.render("(empty) - drop files here", True, (150, 130, 180)), (inner.x + 8, inner.y + 6))
            return
        self._scroll_list(0)
        surf.set_clip(inner)
        for row in range(self.list_rows):
            track_index = self._list_scroll + row
            if track_index >= len(player.playlist):
                break
            y = inner.y + 2 + row * 20
            rowrect = pygame.Rect(inner.x + 2, y, inner.w - 4, 19)
            if track_index == player.index:
                surf.blit(self._gradient(rowrect.size, [(255, 113, 206), (90, 30, 140)]), rowrect)
                col = (255, 255, 255)
            elif rowrect.collidepoint(self._mouse):
                surf.fill((70, 30, 110, 200), rowrect)
                col = (230, 220, 255)
            else:
                col = (170, 255, 220)
            surf.blit(fonts.ui.render(f"{track_index + 1:02d}  {player.playlist[track_index].title}", True, col), (rowrect.x + 6, y + 2))
        surf.set_clip(None)

    def _draw_idle(self, surf):
        fonts = self.fonts
        window_rect = self.idle_win
        self._window(surf, window_rect, "INSERT_DISK.EXE")
        head = fullwidth("DROP MUSIC HERE") if fonts.wide else "DROP MUSIC HERE"
        big = fonts.big.render(head, True, PINK)
        if big.get_width() > window_rect.w - 30:
            big = pygame.transform.smoothscale(big, (window_rect.w - 30, int(big.get_height() * (window_rect.w - 30) / big.get_width())))
        surf.blit(big, big.get_rect(center=(window_rect.centerx, window_rect.y + 70)))
        lines = ["drag audio files or folders onto this window", "mp3  ogg  flac  wav",
                 "[O] browse files    [SHIFT+O] folder    [F1] help"]
        for i, line in enumerate(lines):
            img = fonts.ui.render(line, True, (220, 210, 255) if i != 1 else CYAN)
            surf.blit(img, img.get_rect(center=(window_rect.centerx, window_rect.y + 116 + i * 20)))

    def _draw_help(self, surf):
        width, height = surf.get_size()
        fonts = self.fonts
        window_rect = pygame.Rect(0, 0, 470, 50 + len(HELP_LINES) * 20)
        window_rect.center = (width // 2, height // 2)
        self._window(surf, window_rect, "HELP.TXT")
        for i, (key, desc) in enumerate(HELP_LINES):
            y = window_rect.y + 34 + i * 20
            surf.blit(fonts.bold.render(key, True, YELLOW), (window_rect.x + 16, y))
            surf.blit(fonts.ui.render(desc, True, (230, 220, 255)), (window_rect.x + 150, y))

    def _draw_title_card(self, screen, dt):
        if self._title_timer <= 0 or self._title_scene is None:
            return
        self._title_timer -= dt
        fade = clamp01(min(self._title_timer / 0.8, (3.0 - self._title_timer) / 0.4))
        fonts = self.fonts
        width, height = screen.get_size()
        name = fullwidth(self._title_scene.name) if fonts.wide else self._title_scene.name
        main = fonts.big.render(name, True, (255, 255, 255))
        if main.get_width() > width - 40:
            shrink = (width - 40) / main.get_width()
            main = pygame.transform.smoothscale(main, (width - 40, int(main.get_height() * shrink)))
        cyan = main.copy()
        cyan.fill(CYAN + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        pink = main.copy()
        pink.fill(PINK + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        cy = int(height * 0.2)
        rect = main.get_rect(center=(width // 2, cy))
        for img, off in ((cyan, (-3, 0)), (pink, (3, 2)), (main, (0, 0))):
            img.set_alpha(int(255 * fade))
            screen.blit(img, rect.move(off))
        if fonts.jp and self._title_scene.tagline:
            sub = fonts.jp.render(self._title_scene.tagline, True, YELLOW)
            sub.set_alpha(int(220 * fade))
            screen.blit(sub, sub.get_rect(center=(width // 2, rect.bottom + 18)))

    def _draw_toast(self, screen, dt):
        if self._toast_timer <= 0:
            return
        self._toast_timer -= dt
        img = self.fonts.bold.render(self._toast, True, MINT)
        img.set_alpha(int(255 * clamp01(self._toast_timer / 0.5)))
        width, _ = screen.get_size()
        bg = pygame.Surface((img.get_width() + 20, img.get_height() + 10), pygame.SRCALPHA)
        bg.fill((10, 2, 24, int(200 * clamp01(self._toast_timer / 0.5))))
        toast_rect = bg.get_rect(midtop=(width // 2, 16))
        screen.blit(bg, toast_rect)
        screen.blit(img, img.get_rect(center=toast_rect.center))
