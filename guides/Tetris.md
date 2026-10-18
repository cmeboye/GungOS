# Tetris

Open Apps → Games → Tetris. The game uses the system accent and small GungOS
logo. Its compact footer shows F2 Settings and F9 Help; detailed bindings live
in a scrollable help page.

| Key | Action |
|---|---|
| Left / Right | Move |
| Up / Z | Rotate clockwise / counter-clockwise |
| Down | Soft drop |
| Enter / Space | Hard drop; Enter restarts after game over |
| C | Hold/swap in Modern mode, once per placed piece |
| P | Pause/resume |
| F2 | Settings |
| F3 / F4 | Toggle music / sound effects |
| F5 | New game; confirms during active play |
| F9 | Open/close help |
| Esc | Return from a menu, or leave from the game screen |

Help scrolls with Up/Down, pages with Left/Right and jumps with Home/End
(or Ctrl-Up/Ctrl-Down). Help opened inside Settings returns to that same row.
Menus pause audio, gravity and lock delay. Closing a menu preserves manual
pause and the remaining time before the next fall/lock.

## Settings and modes

Modern remains the default: three next-piece previews and a hold slot.
Classic shows one next piece and disables hold. Both retain the current
seven-bag generator, SRS kicks, ghost outline, scoring and 500 ms lock delay;
Classic is this rule configuration, not an exact NES emulation.

Changing mode requires confirmation and starts a new game. Cancel or a failed
save keeps the board and mode. Music and sound effects switch independently;
volume offers 0/25/50/75/100%. Block styles are Pixel, Bevel and Solid.

Settings are saved in `picoware/settings/picoware.json` under `tetris_mode`,
`tetris_music`, `tetris_sfx`, `tetris_volume` and `tetris_blocks`. Existing
`tetris_sound` preferences remain compatible; the old mute value supplies the
initial music/FX defaults when their separate keys are missing. No preference
writes happen during ordinary gameplay.

## Statistics and block assets

The left panel shows all seven pieces and their counts. Counts increase when
a new piece enters play from the queue, including the first piece and a new
piece after initially filling Hold. Retrieving/swapping a held piece does not
increase counts. Failed spawns are not counted. A new game resets the counts;
the total is displayed below the list.

BEST shows the record for the active mode. Classic and Modern records are saved
separately in `/tetris_scores.json` on the Pico's internal flash, independent of
the SD card. New records are saved at game over, restart, mode change, pause,
opening Settings/Help, and leaving the game. Switching modes saves the outgoing
run under its original mode. Turning off power during uninterrupted play can
lose an unsaved record; pause first to save it. Unchanged records cause no writes.
A failed write keeps the previous file and the new in-memory record, displays an
error, and retries at the next save point. Malformed or missing records start at
zero. The simulator stores this file in the `.flash` folder beside its SD folder.

Each level chooses a palette from a cycle of ten colour families. Existing
placed blocks and previews change to the current palette together. The frame,
menus and controls continue to use the system theme.

Original 8×8 indexed pixel artwork and palettes live in
`builds/MicroPython/apps_unfrozen/engtools/system/tetris_tiles.py`. They compile
with the shared SD package; no PNG loading or external texture files are needed.
The renderer caches only current-level/current-style RGB565 tiles at the board,
preview and statistics sizes and uses native bitmap blits. At 320×320 the pixel
buffers stay below 4 KiB; a level/style change discards the previous cache.

## Updating and testing

This update is SD application code. Update `games/Tetris.mpy` and the complete
`engtools` package together, including `system/pcm.mpy`, `sfx.mpy` and the new
`tetris_tiles.mpy` and `tetris_scores.mpy`. An existing GungOS UF2 with `picoware_pcm` is sufficient.
Optional recordings remain separate; see [TetrisAudio.md](TetrisAudio.md).

Run the simulator with `--viewer --game Tetris --audio real`. Tests:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_tetris_ui.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_tetris_scores.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_tetris_audio.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_release_demos.py
```

UI screenshots are saved under `/private/tmp/gungos-tetris-previews`. Audio
tests generate synthetic WAV files and do not depend on private recordings.
Device speaker output and frame rate still need PicoCalc testing.
