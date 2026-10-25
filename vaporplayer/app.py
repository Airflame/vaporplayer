"""Window, main loop and keyboard controls."""
from __future__ import annotations

import sys

import numpy as np
import pygame

from .audio import AUDIO_EXTENSIONS, Analyzer, Player
from .palette import CYAN, PINK, YELLOW, gradient_lut
from .ui import UI
from .visuals import PostFX, VisualEngine

WINDOW_SIZE = (1280, 720)


def ask_paths(folder: bool = False) -> list[str]:
    """Native file/folder picker via tkinter (blocks while open; audio keeps playing)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return []
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if folder:
            chosen = filedialog.askdirectory(title="Choose a music folder")
            return [chosen] if chosen else []
        pattern = " ".join(f"*{extension}" for extension in sorted(AUDIO_EXTENSIONS))
        return list(filedialog.askopenfilenames(title="Choose music",
                                                filetypes=[("Audio", pattern), ("All files", "*.*")]))
    finally:
        root.destroy()


def use_own_taskbar_identity():
    """Without this, Windows groups the window under python.exe and shows Python's
    icon in the taskbar instead of ours."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vaporplayer.app")
    except (AttributeError, OSError):
        pass


def make_icon() -> pygame.Surface:
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    rows = gradient_lut([YELLOW, PINK, (200, 40, 190)], 32, cyclic=False)
    for y in range(32):
        dx = int((max(0, 15.5 ** 2 - (y - 15.5) ** 2)) ** 0.5)
        if y > 16 and y % 4 == 0:
            continue  # sun stripes
        pygame.draw.line(icon, tuple(int(channel) for channel in rows[y]), (16 - dx, y), (15 + dx, y))
    pygame.draw.line(icon, CYAN, (0, 31), (31, 31), 2)
    return icon


class App:
    def __init__(self, paths: list[str]):
        use_own_taskbar_identity()
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        pygame.display.set_caption("VAPORPLAYER")
        pygame.display.set_icon(make_icon())
        self.windowed_size = WINDOW_SIZE
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.fullscreen = False

        self.player = Player()
        self.analyzer = Analyzer(rate=pygame.mixer.get_init()[0])
        self.visuals = VisualEngine()
        self.fx = PostFX()
        self.ui = UI(self.player, self.visuals, actions={
            "quit": self.quit, "open": self.open_files, "auto": self.toggle_auto,
        })
        self.clock = pygame.time.Clock()
        self.running = True
        if paths:
            self.add(paths)
        self.ui.announce_scene(self.visuals.current)

    # ---------------------------------------------------------------- actions
    def quit(self):
        self.running = False

    def add(self, paths):
        added = self.player.add(paths)
        self.ui.toast(f"+{added} track{'s' if added != 1 else ''}" if added else "no playable audio found")

    def open_files(self, folder: bool = False):
        paths = ask_paths(folder)
        if paths:
            self.add(paths)
        self.clock.tick()  # don't count the time spent in the dialog as one huge frame

    def toggle_auto(self):
        self.visuals.auto = not self.visuals.auto
        self.ui.toast(f"auto visuals {'on' if self.visuals.auto else 'off'}")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode(pygame.display.get_desktop_sizes()[0], pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.ui.fullscreen = self.fullscreen

    def on_key(self, ev):
        key, shift = ev.key, ev.mod & pygame.KMOD_SHIFT
        player, visuals, ui = self.player, self.visuals, self.ui
        if key == pygame.K_SPACE:
            player.toggle_pause()
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            step = 30 if shift else 5
            player.seek(player.position + (step if key == pygame.K_RIGHT else -step))
        elif key in (pygame.K_UP, pygame.K_DOWN):
            player.set_volume(player.volume + (0.05 if key == pygame.K_UP else -0.05))
            ui.toast(f"volume {int(round(player.volume * 100))}%")
        elif key == pygame.K_n:
            player.next()
        elif key == pygame.K_p:
            player.previous()
        elif key == pygame.K_s:
            player.stop()
        elif key in (pygame.K_v, pygame.K_TAB):
            visuals.previous() if shift else visuals.next()
        elif pygame.K_1 <= key <= pygame.K_9 and key - pygame.K_1 < len(visuals.scenes):
            visuals.select(key - pygame.K_1)
        elif key == pygame.K_a:
            self.toggle_auto()
        elif key == pygame.K_o:
            self.open_files(folder=bool(shift))
        elif key == pygame.K_l:
            ui.toggle_playlist()
        elif key in (pygame.K_f, pygame.K_F11):
            self.toggle_fullscreen()
        elif key == pygame.K_h:
            ui.visible = not ui.visible
        elif key == pygame.K_x:
            self.fx.enabled = not self.fx.enabled
            ui.toast(f"VHS effects {'on' if self.fx.enabled else 'off'}")
        elif key in (pygame.K_F1, pygame.K_SLASH, pygame.K_QUESTION):
            ui.show_help = not ui.show_help
        elif key == pygame.K_DELETE:
            removed = player.remove_current()
            if removed is not None:
                ui.toast(f"removed {removed.title}")
        elif key == pygame.K_ESCAPE:
            if ui.show_help:
                ui.show_help = False
            elif self.fullscreen:
                self.toggle_fullscreen()

    # ---------------------------------------------------------------- loop
    def frame(self, dt: float):
        dropped = []
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.DROPFILE:
                dropped.append(ev.file)
            elif ev.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.get_surface()
            elif self.ui.handle_event(ev):
                continue
            elif ev.type == pygame.KEYDOWN:
                self.on_key(ev)
        if dropped:
            self.add(dropped)

        self.player.update()
        features = self.analyzer.process(self.player, dt)
        screen = pygame.display.get_surface()
        self.visuals.render(screen, features, dt)
        self.fx.apply(screen, features, dt)
        self.ui.draw(screen, features, dt)
        pygame.display.flip()

    def run(self):
        while self.running:
            self.frame(min(self.clock.tick(60) / 1000.0, 0.1))
        pygame.quit()


def main(argv: list[str] | None = None):
    np.seterr(all="ignore")
    App(sys.argv[1:] if argv is None else argv).run()
