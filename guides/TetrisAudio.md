# Optional Tetris audio

The public code and default build do not distribute sound recordings. The
previously supplied Game Boy recordings have no redistribution grant recorded
here; they are preserved privately in `local-backup/audio-originals/`. That
folder and the generated WAV files are ignored by Git. Existing local game/SD
sound files remain available for personal use.

Tetris handles missing audio by muting playback and keeping the game usable.
F3 toggles/retries sound; F4 changes volume. Public clean SD builds disable
sound by default when no recordings are included.

## Prepare your own recordings

Use audio that you own or have permission to redistribute. Place WAV inputs in a
private directory with these names:

`music.wav`, `menu.wav`, `move.wav`, `rotate.wav`, `clear.wav`, `tetris.wav`,
`level.wav`, `game_over.wav`, `line_fall.wav`, `lock.wav`.

With ffmpeg installed:

```sh
python3 tools/convert-tetris-audio.py --input-dir /path/to/your/recordings
python3 tools/compile-engineering-apps.py \
  --mpy-cross /path/to/matching/mpy-cross --include-local-audio
```

Conversion produces mono, 22,050 Hz, signed 16-bit little-endian PCM with standard
WAV headers under `builds/MicroPython/apps_unfrozen/games/tetris_sounds/`. It trims
the quiet music tail and records metadata in an ignored `manifest.json`.
The legacy original filenames are also accepted for local conversion.

`--include-local-audio` requires a complete ten-file set and explicitly includes
it in generated app archives. It does not grant rights to the recordings; review
any resulting archive separately before release. The normal firmware build
omits those recordings, even if local copies exist.

## Playback and tests

The `engtools.system.pcm` player streams fixed-size blocks, validates every WAV
at startup and caches the effect readers. It mixes one music stream and up to
two effects through the native `picoware_pcm` backend. Missing/bad files mute sound
and show a short error while the game remains usable.

`simulator/test_tetris_audio.py` generates synthetic waveforms, so testing does
not require the private recordings. It checks WAV validation, bounded playback,
cue sequencing, repeated effects, pause/mute and cleanup. Physical speaker output
still needs device testing.
