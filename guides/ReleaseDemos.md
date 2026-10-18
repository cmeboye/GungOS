# GungOS demonstrations

## Calculate widget

Choose **System → Settings → Screensaver → Calculator Widget**. This is a
native-size Calculate interface, not a scaled full-screen calculator. It reads
`vm.draw.size`, displays the answer and structured prompt, and keeps no history.

F3 enters widget focus; Enter calculates. Space expands mathematical templates,
Tab moves between slots, F5 clears input, F4 opens variables and F7 opens the
math catalogue. A subsequent F3 opens angle/number-format Options. Escape exits
the widget; F1 returns control to system information. No mode/history menus are
exposed in the widget. The complete six-mode calculator lives in PicoLAB.

## Lorenz screensaver

Open **Apps → Screensavers → Lorenz**. A direct-drawn x/z projection of the
Lorenz attractor uses a 192-point trail (768 bytes), a small fixed integration
step and an eight-frame-per-second drawing cap. It does not import Graph or
Graph3D. Space pauses/resumes, F5 resets and Back/Escape exits.

The display is an animated numerical demonstration, not a precision simulation
or a measured physical signal.

## Tetris

Open **Apps → Games → Tetris**, or launch the simulator with `--game Tetris`.
The rewritten game uses seven-bag selection, SRS wall kicks, a ghost piece,
Modern (three previews/hold) or Classic (one preview/no hold), increasing gravity and a bounded 500 ms lock
delay. Best scores persist in internal flash separately for Classic and Modern;
pause or leave the game to save an unfinished run.

| Key | Action |
|---|---|
| Left / Right | Move |
| Up / Z | Rotate clockwise / counterclockwise |
| Down | Soft drop |
| Enter / Space | Hard drop; Enter restarts after game over |
| C | Hold in Modern mode; once per placed piece |
| P | Pause / resume |
| F5 | New game; asks for confirmation during play |
| F2 | Settings |
| F9 | Scrollable help and all key bindings |
| F3 | Toggle music |
| F4 | Toggle sound effects; volume lives in Settings |
| Escape | Exit the game; return from menus |

Mode, sound and block-style changes use the verified settings pipeline.
The left panel counts newly spawned pieces; block colours follow the level.
See [Tetris.md](Tetris.md) for rules, assets and settings.
The supplied music and effects use streamed mono 22,050 Hz, 16-bit PCM WAVs.
The music skips the recording's quiet tail and loops; effects mix over it, with
music ducking for line clears and other important cues. Pause/mute stop advancing
the music, and exit releases files, buffers and speaker resources.

Optional licensed audio uses `games/tetris_sounds` alongside `Tetris.mpy`; the public/default build omits recordings. Playback requires the new
`picoware_pcm` firmware module; the existing device UF2 does not include it yet.
The simulator supports audible playback with `--audio real`. Physical speaker
output still needs PicoCalc validation. See [Tetris audio](TetrisAudio.md) for
asset mapping, conversion and memory details.
