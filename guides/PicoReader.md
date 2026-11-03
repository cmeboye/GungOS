# PicoReader

Open **Apps → PicoDESK → PicoReader**. Copy `.epub` books or UTF-8 `.txt`
files into `picoware/documents/picoreader/` on the SD card. The app creates
this folder when possible. F2 refreshes the library after copying books. The
standalone PicoReader entry opens the same app.

## Controls

- Up/Down selects a book; Enter opens it.
- Right/Down/Enter turns forward; Left/Up turns back, crossing chapters.
- F3/F4 opens the previous/next chapter.
- F1 adds a bookmark at the current page, or removes one already there.
- F5 lists bookmarks: Up/Down selects, Enter opens and F2 removes.
- F6 cycles the reading font: extra small, small, medium. Extra small is the
  default.
- F2 or Esc returns to the library; Esc from the library exits.
- F9 opens help.

## Saved state

Reading position, bookmarks and the font are kept in
`picoware/settings/picoreader/state.json` and restored after an app exit or a
reset. The library shows `Continue ch …, page …` under a book with a saved
position. Up to 24 bookmarks are kept per book and up to 48 books are tracked.

The app also stores per-chapter page counts in the same file as an incremental
SD page index. Counts are added as chapters are read and are discarded when
the book file size or the reading font changes, because both alter pagination.
Once every chapter has a count, the status line shows whole-book progress and
the library shows the total page count. The saved position and bookmarks
record a word offset, so changing the font keeps them on the same passage
rather than the same page number.

Saving uses a verified temporary file and keeps a `.bak` copy while replacing
the previous state; a missing or damaged main file falls back to that copy.
The state is capped at 32 KB; if the cap is reached, page counts are dropped
before positions and bookmarks.

## Reading position

PicoReader follows the EPUB spine reading order, wraps chapter text to the
screen and uses system colours. Paragraph breaks and basic XML/HTML entities
are supported. Changing the font keeps the reader near the same words rather
than the same page number.

TXT files have no chapters. A text file is split into bounded parts at a line
break where possible; each part behaves like a chapter for navigation and page
turns.

## Supported formats and bounds

This version supports UTF-8 text EPUBs using stored or DEFLATE ZIP compression.
Images, CSS styling, embedded fonts, tables as layouts, links, table-of-contents
menus, search and DRM are not supported. Encrypted resource declarations are
rejected, including font obfuscation.

- EPUB: 32 MiB per book, 1,024 archive entries, 192 KiB per compressed or
  uncompressed chapter, 64 KiB package metadata, 16 KiB container metadata.
- TXT: 8 MiB per file, split into parts of about 96 KiB. A split never breaks
  a UTF-8 character.
- Oversized sections report an error; split large chapters before using the
  book.
- Files are read directly from the archive without extracting files onto the
  SD.

App changes can be deployed with the normal desktop app bundle and matching
MicroPython bytecode compiler. No new firmware module is required; the firmware's
`deflate` module provides decompression. Physical SD/display validation is still
required before treating this as a device-qualified release.

Generate three original dummy EPUBs and one TXT sample with
`python3 tools/build-reader-samples.py`. They are placed in the simulator SD
and both local SD staging trees: Getting Started, The Lantern Walk (multiple
pages and chapters), Field Notes (punctuation, accents, long words and a short
final chapter), and Pocket Notes (plain text).
