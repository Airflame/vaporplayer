# ＶＡＰＯＲＰＬＡＹＥＲ

A vaporwave music player with psychedelic visuals that react to the music.

```
pip install -r requirements.txt
python main.py                      # then drop files/folders onto the window, or press O
python main.py song.mp3 ~/Music     # or pass files / folders directly
```

Plays mp3, ogg, flac and wav.

## Visuals

Every scene is driven by a live FFT of the exact samples being played. That gives a 48-band
log spectrum, bass/mid/treble energy, spectral brightness and beat detection.

| # | Scene | What reacts |
|---|-------|-------------|
| 1 | **OUTRUN SUNSET** | sun pulses with bass, mountains are the spectrum, grid speed follows energy, stars twinkle with treble |
| 2 | **DREAM KALEIDOSCOPE** | mirrored plasma warps with bass/mids, beats send out light rings, segment count shifts every 32 beats |
| 3 | **CYBER TUNNEL** | curving wireframe tunnel, rings bulge per band, flight speed follows energy |
| 4 | **LIQUID MEMORY** | Milkdrop-style feedback: waveform halo, stereo goniometer, a breathing wire globe, beat shockwaves |

On top of the scenes there is VHS post-processing: RGB split on beats, tracking tears, noise,
vignette and scanlines. In auto mode the player moves to the next scene on a beat every ~40 s.

## Controls

| Key | Action |
|-----|--------|
| Space | play / pause |
| ← / → | seek 5 s (Shift: 30 s) |
| ↑ / ↓ | volume |
| N / P | next / previous track |
| S | stop |
| V / Tab | next visual (Shift: previous) |
| 1–4 | pick a visual |
| A | auto-cycle visuals |
| O / Shift+O | open files / folder |
| L | playlist |
| Delete | remove the current track from the playlist (the next one starts) |
| F / F11 | fullscreen |
| H | hide interface |
| X | VHS effects on/off |
| F1 | help |

You can drag the player, playlist and "insert disk" windows by their title bars; clicking a window
brings it to the front. While music plays, the interface fades out after a few seconds without mouse movement.

## Layout

- `vaporplayer/audio.py`: decoding, playback/seeking, spectrum and beat analysis
- `vaporplayer/visuals/`: one module per scene, plus `postfx.py` and the crossfading `VisualEngine`
- `vaporplayer/ui.py`: retro-OS windows, LCD, transport, playlist
- `vaporplayer/app.py`: window, main loop and keyboard controls

To add a scene, subclass `visuals.base.Scene`, implement `draw(surf, features, dt)` and add it
to `VisualEngine.scenes`.
