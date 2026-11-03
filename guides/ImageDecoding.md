# JPEG review and PNG integration — 3 November 2026

## JPEG findings and applied changes

The native JPEGDEC library already supports reduced IDCT decoding at 1, 1/2,
1/4 and 1/8 resolution and submits RGB565 tiles to the existing RGB332 display
surface. It does not need a second full decoded image in the Python heap.
The review focused on the wrapper, SD transport and tile handoff.

| Finding | Change |
|---|---|
| In-memory JPEGs allocated two 8 KiB streaming buffers; BytesIO copied mutable input | Borrow the original buffer and call synchronous native decode directly. Small files also use this path. |
| JPEG headers were parsed twice, including Huffman-table initialization | A bounded marker scan finds baseline dimensions; native header initialization runs once on updated firmware. Legacy streaming retains its compatibility probe. |
| SD read counts were ignored, exposing stale tail bytes | Fill buffers across short reads, track actual lengths and publish only valid bytes. |
| Sequential reads unnecessarily sought for every buffer | Track the file position; seek only when a request changes position. |
| Decode returned the successful start result even if the worker later failed | Return the final decode result and retain a diagnostic. |
| Startup could be polled before core 1 marked itself running | Mark running before launch; add inter-core publication/acquisition barriers. |
| Only 1024 bytes of the reserved 4096-byte worker stack were passed to the SDK | Pass `sizeof(core1_stack)`; reserved RAM size is unchanged. |
| Header initialization could wait for Python input while Python was blocked in the initializer | Initialize against the bounded prefix in RAM before switching to streaming callbacks. |
| Split reads could request beyond EOF and seek clamped to the last byte | Clamp reads to remaining input; EOF reads return zero; allow seeking exactly to EOF. |
| Input failures could leave a worker running or buffers retained | Cleanup on all paths; explicit close; owned GUI decoders release buffers/context. |
| Idle checks polled an unrelated multicore FIFO with a 100 us timeout | Use the decoder's existing shared completion state. |
| Python polling allocated tuples in an unbounded hot loop | Yield while waiting and enforce a bounded inactivity timeout. |
| Odd-width JPEG tiles included padding outside the image | Respect `iWidthUsed` while retaining the source stride; full tiles still use one blit. |
| Fit calculations rounded down and silently clipped images larger than 1/8 permits | Use ceiling dimensions, respect available viewport and reject oversized images clearly. |
| Simulator JPEG drawing used an unmapped BMP path, unsupported 16-bit BMPs and treated successful None as failure | Use mapped SD paths, 24-bit helper BMP output and the native BMP return contract. |

Validation:

- `python3 tools/tests/test_jpeg.py`: generated original baseline fixtures,
  native JPEGDEC tile/stride/pixel bounds at all four scales, actual GUI decoding,
  direct/file equality, malformed/progressive inputs and lifecycle.
- Transport tests cover short reads, exact and partial final buffers, repeated
  use, native failure, launch exceptions, legacy header probing and stall cleanup.
- Controlled desktop MicroPython input-path probe with a 65536-byte bytearray:
  additional Python allocations observed during the old call were **82432 bytes**;
  the new call used **896 bytes**. Both probes replaced the codec operation with
  a measurement hook. These figures exclude already allocated native context,
  codec execution and display storage, and are not device decode timings.
- Native graphics checks: 6018 passed. Menu/header and reader memory regressions
  passed. The modified PicoCalc firmware builds successfully.

Native fixes and the frozen Python wrapper require a new UF2. Existing v1.35
releases are preserved. Actual SD throughput, multicore behavior and latency
remain pending physical testing; there is no claimed device speedup percentage.

## JPEG limits and next measurements

- Baseline Huffman JPEG only in the supported GUI path; progressive/extended
  modes fail cleanly. EXIF orientation/thumbnail selection is not implemented.
- File streaming requires the complete header in the first input buffer. Large
  APP/EXIF prefixes fail instead of deadlocking. A future native file/stream
  initializer can remove this prefix limit without growing Python buffers.
- Inputs too large to fit even at 1/8 scale are rejected. Exact arbitrary-size
  resampling and zoom/pan remain separate work.
- Keep the 2x8 KiB streaming default until device measurements compare 2, 4 and
  8 KiB buffers on the same SD card. Smaller buffers save heap but can increase
  SD request overhead; host timings do not settle that tradeoff.
- The native context is still significant. Reuse a decoder for repeated images,
  or close it explicitly; GUI convenience methods close their owned instance.

## PNG implementation and RAM allocation

The Pico 2 W has fast internal SRAM and this board also has 8 MiB of serial
PSRAM. PSRAM is not mapped into the CPU address space: native decoder pointers
cannot simply point into it. GungOS already keeps its default RGB332 screen
buffer there. The buffered reader selects that mode while a book is open,
even if Fast Drawing is enabled, then restores the previous mode at the library.

The pinned [PNGdec](https://github.com/bitbank2/PNGdec) revision is
`2855e785bc1a80763c89a2afd808faf6156d35c6` (1.1.7). The vendored fork of zlib
accepts caller-owned state and a fixed 32 KiB history window. GungOS uses that
inflater with its own bounded PNG parser, filter reconstruction and RGB332
compositor. The upstream parser/converter is not compiled: review found
incomplete chunk integrity checks, packed odd-width output overruns and missing
transparency paths. The inflater's optional unaligned word-copy path also
overshoots a short output buffer; our local patch selects its bounded byte-copy
fallback. See `src/MicroPython/png/upstream/SOURCE.md` and preserved licenses.

The **entire native workspace is capped at 48 KiB at compile time**, including
inflate state, its 32 KiB window, two source rows, a 1 KiB input buffer, palette,
alpha table and a 320-byte output row. Desktop measurement is **48,664 bytes**;
**48,552 bytes on the PicoCalc firmware build**. This is workspace size, not the complete
reader heap requirement. The compressed image and a full decoded source image
are never retained in the Python heap.

The buffered reader keeps only bounded page caches and a suspended text stream
while decoding; no full chapter is retained. A rendered 320x280
RGB332 preview occupies **89,600 bytes of managed PSRAM**, in addition to the
existing 102,400-byte screen surface. The new `picoware_psram.alloc_buffer(n)`
reserves external storage without first making an equally large SRAM object.
Read/write operations use rows, and look up the managed object's current address
after any compaction. Explicit close releases the preview and restores the
previous drawing mode. Preview caches are session-local and cannot become
stale across books or themes.

EPUB resources are streamed to one private temporary SD file. Stored and raw
DEFLATE entries are size/CRC checked; native deflate extraction reuses the same
workspace in a separate call before image decoding. No decoder and extractor
workspace overlap. Partial and completed temporary files are removed on failure
and after use respectively. The ZIP footer is scanned in overlapping 1 KiB
blocks, avoiding a 64 KiB allocation for larger books and long ZIP comments.

## Supported PNGs and bounds

- Non-interlaced grayscale and indexed colour at 1, 2, 4 or 8 bits; RGB,
  grayscale+alpha and RGBA at 8 bits per channel. Palette alpha and grayscale/RGB
  `tRNS` keys are composited against the reader background with rounded alpha.
- All five PNG filters; all chunk CRCs and the zlib checksum are checked.
  Invalid palette indices, scanline counts, trailing compressed data, unknown
  critical chunks and truncation fail explicitly.
- At most 4 MiB per image resource, 2,048 source pixels wide, 4,096 high,
  4,194,304 source pixels and 3,072 bytes per source row. The row limit means
  RGB width up to 1,024 and RGBA up to 768; narrow/packed formats can be wider.
- Output fits within 320x280, retains aspect ratio, centres and uses nearest
  neighbour reduction. Every source row is reconstructed; only selected pixels
  are converted. No upscale, zoom/pan, gamma correction or animation playback.
- Adam7 interlace and 16-bit channels report an unsupported-format error.
  SVG files are listed but not rasterized. Desktop preparation for oversized
  images, SVG and interlacing remains future work.

## PicoReader image controls and validation

Press **F7** while reading to list up to 32 distinct images from the current
chapter, in document order. Both HTML `img` and SVG `image` references work;
relative paths, encoded spaces and alt/title captions are supported. Remote
resources are skipped. Enter opens an image; Left/Right selects the previous or
next image. Esc returns to the image list, then to the same text position.
Image-only cover chapters can be viewed this way. Images are not inserted into
the existing text pagination, so word anchors and bookmarks remain stable.

Checks:

- `python3 tools/tests/test_png.py`: 84 native pixel/integrity/bounds cases with
  AddressSanitizer and UndefinedBehaviorSanitizer. Covers all supported colour
  types/depths, filters, odd widths, alpha/transparent keys, arbitrary IDAT
  splits, source limits, extreme aspect ratios and damaged input.
- `python3 tools/tests/test_reader_images.py`: original illustrated EPUB through
  the actual native PNG/ZIP bindings and existing native JPEG simulator helper;
  short reads, exceptions and repeated cleanup, deflated/stored resources, a
  60 KiB ZIP comment, PSRAM preview replay and reading-position restoration.
- Existing reader UI/state and constrained native-heap checks remain required.
  These measurements exclude physical SD latency and external-memory timing.

Native PNG/PSRAM additions and frozen GUI changes need a matching new UF2,
plus the updated SD app bundle. Actual PicoCalc qualification is pending.

The buffered-reader preview keeps the bounded page cache and one suspended text
stream during image viewing, and resumes the same cached page on return. F7
image-reference discovery now scans the chapter incrementally without the old
192 KiB chapter ceiling, although the menu action itself is synchronous.
