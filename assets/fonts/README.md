# GungOS fonts

Spleen is the default bitmap face. The original STMicroelectronics font tables
are preserved byte-for-byte in `legacy-stm32/`, including their license headers.
The desktop native build includes the device tables, and the Python simulator
reads those same tables.

The pinned upstream BDF sources, BSD 2-Clause license, revision and source hashes
are in `spleen/`. Regenerate with `python3 tools/convert-spleen-fonts.py`; verify
with `python3 tools/convert-spleen-fonts.py --check`.

| GungOS slot | Existing cell | Spleen source |
|---|---|---|
| Extra small | 5x8 | 5x8 |
| Small | 7x12 | 6x12 |
| Medium | 11x16 | 8x16 |
| Large | 14x20 | 8x16 |
| Extra large | 17x24 | 12x24 |

Glyphs are centered with blank padding, without rescaling. Existing widths,
heights, spacing and ASCII 32–126 indexing remain unchanged. Spleen does not
provide a 20-pixel face; the large slot uses the 16-pixel face with vertical
padding. Unicode support is not added by this conversion.

To restore the previous face, copy the five `legacy-stm32/font*.c` files into
`src/MicroPython/font/` and rebuild. No application changes are needed.

Native device fonts are compiled into the firmware: trying this on PicoCalc
requires a newly built UF2; an SD-only application update cannot change them.
