# PicoDict

Open Apps → PicoDESK → PicoDict. This first version translates one English or
Italian word offline. Enter searches; F2 switches direction; F5 clears; Left/Right
move the cursor; Back/Del erase before it. F9 opens help and Esc returns.
Typing or changing direction clears the previous result so it cannot be mistaken
for the current query. Accents matter; case and curly apostrophes are normalized.
Conjugation tables, stemming, suggestions and sentence translation are deferred.

## Build and install

Obtain WikDict's two developer SQLite databases from
https://download.wikdict.com/dictionaries/sqlite/2/ (`en-it.sqlite3` and
`it-en.sqlite3`). Preserve the originals to allow future richer imports.

```sh
python3 tools/build-dictionary.py --en-it /path/en-it.sqlite3 --it-en /path/it-en.sqlite3
python3 tools/compile-engineering-apps.py --mpy-cross .build/mpy-cross/mpy-cross --snapshot sd-card/picoware/apps
```

Merge **both** `builds/MicroPython/DesktopApps-preview.zip` and
`builds/MicroPython/PicoDict-data.zip` into the SD root. The app archive contains
PicoDict and the updated PicoDESK launcher; the separate data archive contains
`picoware/dictionary/`. The generated `sd-card/` tree also contains both.
Restart after replacing modules. Existing GungOS v1.34 firmware supports this SD
app; no new UF2 is required. Raw SQLite databases are not installed on the Pico.
Data is intentionally a separate package: rebuilding app code does not require
repacking the dictionary, and app-only updates do not remove installed data.

## Data and limitations

WikDict by Karl Bartel uses Wiktionary contributor data via DBnary, under
CC BY-SA 4.0: https://www.wikdict.com/page/download and
https://creativecommons.org/licenses/by-sa/4.0/ . Generated data includes a notice
and a manifest with source/output SHA-256 hashes, counts and format version.
The adapted dictionary data stays under CC BY-SA 4.0, separately from app code.

The converter reads `simple_translation`, normalizes headwords, retains English/
Italian alphabetic words (including accents, hyphens and apostrophes), and picks
the first eligible single-word translation in the source's ordered list. For
case-colliding headwords, it prefers the row with the larger `max_score`.
It drops phrases and entries with no single-word equivalent. This is a source
ordering heuristic, not a guarantee of the most common or contextually correct
sense. Proper names and uncommon terms can occur in the source. Inflected forms
work only when explicitly included. No grammatical metadata is invented.

Format: 8-byte `PDICT01\0` magic, little-endian uint32 record count, followed by
128-byte records: 64-byte normalized UTF-8 key and 64-byte UTF-8 translation,
both zero-padded. Fields must be shorter than 64 bytes and are never truncated.
Records sort by UTF-8 key bytes. Binary search reads at most one 128-byte record
per step; no full dictionary or index is loaded into RAM. Fixed records trade
SD space for simple bounded reads. Each lookup validates header and file size.

## Verification

Run `builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_dictionary.py`.
It checks bounded lookups, missing words, invalid input, truncated data, both
supplied dictionaries when built, PicoDESK launch, keyboard controls, help,
missing SD data and exit cleanup. Actual SD latency and free heap still need
checking on PicoCalc; host simulator timings do not establish hardware speed.
