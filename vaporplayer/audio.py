"""Audio loading, playback and real-time spectrum analysis."""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame

AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac"}


def collect_audio_files(paths) -> list[Path]:
    """Expand files and folders (recursively) into a sorted list of audio files."""
    found: list[Path] = []
    for path in paths:
        path = Path(path)
        if path.is_dir():
            found.extend(sorted(file for file in path.rglob("*") if file.suffix.lower() in AUDIO_EXTENSIONS))
        elif path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            found.append(path)
    return found


@dataclass
class Track:
    path: Path

    @property
    def title(self) -> str:
        return self.path.stem.replace("_", " ")


@dataclass
class LoadedTrack:
    track: Track
    samples: np.ndarray  # raw samples in the mixer's format, (n,) or (n, channels)
    mono: np.ndarray     # (n,) float32 in [-1, 1], used for analysis
    scale: float         # divisor that maps `samples` into [-1, 1]
    rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.rate


def load_track(track: Track) -> LoadedTrack:
    rate = pygame.mixer.get_init()[0]
    sound = pygame.mixer.Sound(str(track.path))
    samples = pygame.sndarray.array(sound)
    del sound
    if np.issubdtype(samples.dtype, np.integer):
        scale = float(np.iinfo(samples.dtype).max) + 1.0
    else:
        scale = 1.0
    as_float = samples.astype(np.float32)
    mono = as_float.mean(axis=1) if as_float.ndim == 2 else as_float
    return LoadedTrack(track, np.ascontiguousarray(samples), (mono / scale).astype(np.float32), scale, rate)


class Player:
    """Playlist + playback. Tracks are decoded fully into memory so we can
    analyse the exact samples being heard and seek anywhere."""

    def __init__(self):
        self.playlist: list[Track] = []
        self.index = -1
        self.current: LoadedTrack | None = None
        self.paused = False
        self.volume = 0.8
        self.loading = False
        self.status = ""
        self._sound = None
        self._channel = None
        self._offset = 0.0       # track position at which the current sound started
        self._started_at = 0.0   # perf_counter() when it started
        self._paused_at = 0.0
        self._token = 0
        self._pending: list = []
        self._lock = threading.Lock()
        self._failures = 0

    # ---------------------------------------------------------------- playlist
    def add(self, paths) -> int:
        files = collect_audio_files(paths)
        first_new = len(self.playlist)
        self.playlist.extend(Track(file) for file in files)
        if files and self.current is None and not self.loading:
            self.play_index(first_new)
        return len(files)

    def play_index(self, index: int):
        if not self.playlist:
            return
        index %= len(self.playlist)
        if index == self.index and self.current is not None:
            self.paused = False
            self._start(0.0)
            return
        self._halt()
        self.current = None
        self.index = index
        self.paused = False
        self.loading = True
        self._token += 1
        threading.Thread(target=self._load_worker, args=(self._token, self.playlist[index]),
                         daemon=True).start()

    def remove_current(self) -> Track | None:
        """Drop the current track from the playlist and start the one that took its place."""
        if not 0 <= self.index < len(self.playlist):
            return None
        removed = self.playlist.pop(self.index)
        self._halt()
        self.current = None
        self.loading = False
        self._token += 1  # discard a load that may still be in flight
        if self.playlist:
            self.play_index(self.index % len(self.playlist))
        else:
            self.index = -1
            self.paused = False
        return removed

    def _load_worker(self, token: int, track: Track):
        try:
            result = load_track(track)
        except Exception as exc:  # unreadable / unsupported file
            result = exc
        with self._lock:
            self._pending.append((token, result))

    def update(self):
        with self._lock:
            pending, self._pending = self._pending, []
        for token, result in pending:
            if token != self._token:
                continue  # the user already moved on to another track
            self.loading = False
            if isinstance(result, Exception):
                self.status = f"can't play {self.playlist[self.index].path.name}: {result}"
                self._failures += 1
                if self._failures < len(self.playlist):
                    self.next()
            else:
                self._failures = 0
                self.status = ""
                self.current = result
                self._start(0.0)
        if self.current and not self.paused and self.position >= self.current.duration - 0.02:
            self.next()

    # ---------------------------------------------------------------- transport
    def _halt(self):
        if self._channel is not None:
            self._channel.stop()
        self._channel = None
        self._sound = None

    def _start(self, pos: float):
        lt = self.current
        pos = min(max(0.0, pos), max(0.0, lt.duration - 0.05))
        self._halt()
        self._sound = pygame.sndarray.make_sound(lt.samples[int(pos * lt.rate):])
        self._channel = self._sound.play()
        if self._channel is not None:
            self._channel.set_volume(self.volume)
        self._offset = pos
        self._started_at = time.perf_counter()
        if self.paused:
            if self._channel is not None:
                self._channel.pause()
            self._paused_at = pos

    @property
    def position(self) -> float:
        if self.current is None:
            return 0.0
        if self.paused:
            return self._paused_at
        return min(self._offset + time.perf_counter() - self._started_at, self.current.duration)

    @property
    def duration(self) -> float:
        return self.current.duration if self.current else 0.0

    @property
    def playing(self) -> bool:
        return self.current is not None and not self.paused

    def toggle_pause(self):
        if self.current is None:
            if self.playlist and not self.loading:
                self.play_index(max(self.index, 0))
            return
        if self.paused:
            self.paused = False
            self._offset = self._paused_at
            self._started_at = time.perf_counter()
            if self._channel is not None:
                self._channel.unpause()
        else:
            self._paused_at = self.position
            self.paused = True
            if self._channel is not None:
                self._channel.pause()

    def stop(self):
        if self.current is not None:
            self.paused = True
            self._start(0.0)

    def seek(self, pos: float):
        if self.current is not None:
            self._start(pos)

    def next(self):
        if self.playlist:
            self.play_index(self.index + 1)

    def previous(self):
        if self.current is not None and self.position > 3.0:
            self.seek(0.0)
        elif self.playlist:
            self.play_index(self.index - 1)

    def set_volume(self, volume: float):
        self.volume = max(0.0, min(1.0, volume))
        if self._channel is not None:
            self._channel.set_volume(self.volume)


@dataclass
class AudioFeatures:
    """Everything the visuals know about the music, all roughly in [0, 1]."""
    bands: np.ndarray        # smoothed log-spaced spectrum
    wave_left: np.ndarray    # recent waveform, [-1, 1]
    wave_right: np.ndarray
    bass: float = 0.0
    mid: float = 0.0
    treble: float = 0.0
    energy: float = 0.0
    intensity: float = 0.0   # slow-moving energy: the "mood" of the section
    centroid: float = 0.5    # spectral brightness
    beat: bool = False       # true on the frame a beat is detected
    beat_pulse: float = 0.0  # 1.0 on a beat, decaying afterwards
    beat_count: int = 0
    time: float = 0.0
    live: bool = False       # driven by real music (not idle/demo)


class Analyzer:
    FFT_SIZE = 2048
    WAVE_POINTS = 256

    def __init__(self, rate: int = 44100, n_bands: int = 48):
        self.rate = rate
        self.n_bands = n_bands
        self._window = np.hanning(self.FFT_SIZE).astype(np.float32)
        freqs = np.fft.rfftfreq(self.FFT_SIZE, 1.0 / rate)
        edges = np.geomspace(32.0, min(16000.0, rate / 2.2), n_bands + 1)
        idx = np.searchsorted(freqs, edges)
        for i in range(1, len(idx)):
            idx[i] = max(idx[i], idx[i - 1] + 1)
        self._edges = idx
        centres = np.sqrt(edges[:-1] * edges[1:])
        self._tilt = (3.0 * np.log2(centres / 1000.0)).astype(np.float32)  # undo music's natural roll-off
        self._bass_mask = centres < 150
        self._mid_mask = (centres >= 150) & (centres < 2000)
        self._treble_mask = centres >= 2000
        self._log_centres = np.log(centres)
        self.bands = np.zeros(n_bands, np.float32)
        self._agc = 0.6
        self._bass_hist: deque = deque(maxlen=60)
        self._last_beat = -1.0
        self._beat_pulse = 0.0
        self._beat_count = 0
        self._intensity = 0.0
        self.clock = 0.0

    def _analyze(self, lt: LoadedTrack, pos: int, dt: float):
        fft_size = self.FFT_SIZE
        seg = lt.mono[max(0, pos - fft_size):pos]
        if len(seg) < fft_size:
            seg = np.pad(seg, (fft_size - len(seg), 0))
        spec = np.abs(np.fft.rfft(seg * self._window)) / (fft_size / 4)
        mags = np.maximum.reduceat(spec[:self._edges[-1]], self._edges[:-1])
        db = 20.0 * np.log10(mags + 1e-7) + self._tilt
        level = np.clip((db + 62.0) / 56.0, 0.0, 1.0)
        # slow automatic gain so quiet and loud masters both look lively
        self._agc = max(float(level.max()), self._agc - dt * 0.04, 0.35)
        raw = np.clip(level / self._agc, 0.0, 1.0) ** 1.4

        recent = lt.samples[max(0, pos - 1024):pos]
        if len(recent) < 16:
            zero = np.zeros(self.WAVE_POINTS, np.float32)
            return raw, zero, zero
        recent = recent.astype(np.float32) / lt.scale
        if recent.ndim == 1:
            left = right = recent
        else:
            left, right = recent[:, 0], recent[:, -1]
        pick = np.linspace(0, len(left) - 1, self.WAVE_POINTS).astype(int)
        return raw, np.clip(left[pick] * 1.3, -1, 1), np.clip(right[pick] * 1.3, -1, 1)

    def _demo(self):
        """A gentle synthetic signal so the visuals keep dreaming with no music."""
        now = self.clock
        band_pos = np.linspace(0.0, 1.0, self.n_bands, dtype=np.float32)
        kick = math.exp(-((now * 1.6) % 1.0) * 7.0)
        raw = 0.25 + 0.18 * np.sin(now * 0.9 + band_pos * 7) + 0.12 * np.sin(now * 2.3 - band_pos * 13)
        raw *= 1.0 - 0.5 * band_pos
        raw[:10] += 0.45 * kick
        ph = np.linspace(0, math.tau * 3, self.WAVE_POINTS, dtype=np.float32)
        left = 0.45 * np.sin(ph + now * 2) * (0.5 + 0.5 * kick)
        right = 0.45 * np.cos(ph * 1.5 + now * 1.3) * (0.5 + 0.5 * kick)
        return np.clip(raw * 0.8, 0, 1).astype(np.float32), left, right

    def process(self, player: Player, dt: float) -> AudioFeatures:
        self.clock += dt
        lt = player.current
        live = lt is not None and player.playing
        if live:
            raw, wl, wr = self._analyze(lt, int(player.position * lt.rate), dt)
        elif lt is not None or player.loading:  # paused / loading: let everything settle
            raw = np.zeros(self.n_bands, np.float32)
            wl = wr = np.zeros(self.WAVE_POINTS, np.float32)
        else:
            raw, wl, wr = self._demo()

        attack = 1.0 - math.exp(-dt * 30.0)
        release = 1.0 - math.exp(-dt * 7.0)
        self.bands += (raw - self.bands) * np.where(raw > self.bands, attack, release)
        bands = self.bands

        raw_bass = float(raw[self._bass_mask].mean())
        avg = sum(self._bass_hist) / len(self._bass_hist) if self._bass_hist else raw_bass
        self._bass_hist.append(raw_bass)
        beat = (raw_bass > avg * 1.3 + 0.04 and raw_bass > 0.18
                and self.clock - self._last_beat > 0.27)
        if beat:
            self._last_beat = self.clock
            self._beat_pulse = 1.0
            self._beat_count += 1
        else:
            self._beat_pulse *= math.exp(-dt * 5.0)

        energy = float(bands.mean())
        self._intensity += (energy - self._intensity) * (1.0 - math.exp(-dt * 0.8))
        total = float(bands.sum())
        if total > 1e-4:
            lc = self._log_centres
            centroid = (float((bands * lc).sum()) / total - lc[0]) / (lc[-1] - lc[0])
        else:
            centroid = 0.5

        return AudioFeatures(
            bands=bands.astype(np.float64), wave_left=wl.astype(np.float64), wave_right=wr.astype(np.float64),
            bass=float(bands[self._bass_mask].mean()), mid=float(bands[self._mid_mask].mean()),
            treble=float(bands[self._treble_mask].mean()), energy=energy,
            intensity=self._intensity, centroid=centroid, beat=beat,
            beat_pulse=self._beat_pulse, beat_count=self._beat_count,
            time=self.clock, live=live,
        )
