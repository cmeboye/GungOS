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
- F7 lists the current chapter's images. Enter opens one; Left/Right switches
  images. Esc closes the image, then closes the list and restores the text page.
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
record a visible-text character offset, so changing the font keeps them on the
same passage, even inside a very long word. Older word-based positions and
bookmarks still load. The old page-count cache is rebuilt for the new paginator.

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
CSS styling, embedded fonts, tables as layouts, links, table-of-contents
menus, search and DRM are not supported. Encrypted resource declarations are
rejected, including font obfuscation.

- EPUB: classic ZIP files up to 2 GiB minus one byte, 4,096 archive entries,
  64 MiB of uncompressed text per chapter, 2 MiB streamed package metadata and
  16 KiB streamed container metadata. The reading-order index is capped at 512
  entries and 32 KiB of ID/path characters. ZIP64 and multi-disk archives are unsupported.
- TXT: 8 MiB per file, split into parts of about 96 KiB. A split never breaks
  a UTF-8 character.
- Oversized text sections and metadata report an error. The archive size and
  chapter ceilings are validation limits, never allocation sizes.
- Text is read directly from the archive. A selected JPEG/PNG image is streamed
  to a private temporary SD file, checked, decoded and removed. Up to 32 images
  are listed per chapter; image entries are capped at 4 MiB each.
- PNG: non-interlaced grayscale/indexed 1/2/4/8-bit and RGB/RGBA/gray-alpha 8-bit.
  Transparency uses the reader background. Source rows are capped at 3 KiB
  (RGB width 1024, RGBA 768); output fits 320x280. Interlaced/16-bit PNG and SVG
  rasterization are unsupported. See [image limits](ImageDecoding.md).
- JPEG: baseline only, reduced by 1/2, 1/4 or 1/8 as needed. Oversized images
  that still cannot fit are rejected. Progressive JPEG is unsupported.

Text-only changes can be deployed with the desktop app bundle. Image support
requires the matching image-preview firmware as well: it adds the native
`pngdec` module and direct managed PSRAM allocation. The image workspace is
under 48 KiB of SRAM, and the 89,600-byte rendered preview lives in PSRAM.
Only the visible page and bounded page caches are retained while viewing.
Returning from an image restores the cached text without inflating the chapter
again. Reading also selects the external-PSRAM display mode, restoring the
previous mode on exit.
Physical SD/display validation is still pending.

Generate three original dummy EPUBs and one TXT sample with
`python3 tools/build-reader-samples.py`. They are placed in the simulator SD
and both local SD staging trees: Getting Started, The Lantern Walk (multiple
pages and chapters), Field Notes (punctuation, accents, long words and a short
final chapter), and Pocket Notes (plain text).

## Buffered reading (2026-11-03 preview)

The reader streams UTF-8/XHTML text in 512-byte chunks instead of allocating and
wrapping a whole chapter. ZIP metadata uses a 16-entry cache. Idle ticks prepare
three pages ahead, including chapter boundaries; scanning a new ZIP directory
entry also yields regularly. This is cooperative work in the app loop, not a
background thread.

- At most seven page payloads and 16 KiB of UTF-8 page text in the RAM cache.
- At most 64 recently generated pages in a private SD ring cache: 4,096 bytes
  per page plus a 28-byte header, at most 263,936 bytes per session. Font reflow
  can temporarily use a second cache. Both are removed on normal exit.
- One DEFLATE history window, up to 32 KiB, plus a 1 KiB compressed-input buffer.
  The current page, parser/generator state, ZIP/package metadata, application
  objects and the interpreter need additional heap. The 16 KiB cap is a text
  payload cap, not a claim about total reader RAM.
- Cached page turns need no chapter decompression. If keys outrun prefetch,
  `Loading page...` appears while the old page stays visible. At most eight
  additional turns are queued. Esc/F2 can return to the library during loading.
- A jump outside the cache, reopening at a saved passage or changing font may
  replay from the beginning of that chapter. Work yields between chunks, but a
  distant jump in a huge compressed chapter can take time. Random DEFLATE
  restart checkpoints and a persistent page index are not implemented.
- Chapter totals display `?` until the end has actually been read. Whole-book
  progress is available once all chapter totals are known. CRC and exact output
  length are checked when a stream reaches its end; cancelling a partial read
  cannot certify the unread remainder.
- F7 scans the current chapter for up to 32 image references on demand; this
  scan and image decoding are foreground operations and can take time. Images
  retain the existing 4 MiB resource and format limits.

The matching preview UF2 adds a C buffered input adapter so the inflater's
one-byte reads avoid Python callbacks. The SD app has a slower compatibility
path for older firmware with native `deflate`; use the matching UF2 for timing
checks. The original tagged release remains unchanged.

Validation: `python3 tools/tests/test_reader_buffer.py` generates an EPUB above
32 MiB, a chapter above 8 MiB and over 1,024 ZIP assets. It checks boundary-split
UTF-8/entities/comments/tags, font-independent anchors, long words, fast turns,
RAM/SD caps, cached backward turns, distant replay and CRC errors. Native tests
turn 320 pages forward and 75 backward; compiled loader/pager code passes in a
160 KiB heap. That is a loader/pager check, excluding the full UI and physical
SD/display costs. Run the existing reader UI, image and sample-memory tests as
well. Physical qualification remains pending.

## Earlier memory fix after v1.35 device testing

The first v1.35 device test reported frequent allocation failures even with the
supplied sample books, especially while changing chapters. The EPUB loader used
the 192 KiB section ceiling as `DeflateIO.read()`'s allocation size, regardless
of the actual chapter size, and always allocated a 32 KiB history window.

The fix allocates only the declared section length plus one byte (retaining the
oversize check), chooses a safe smaller raw-deflate window for short sections,
collects previous decoder garbage and avoids a per-character entity-decoding
list. Returning to the library releases the old chapter and archive index.
Failed font changes preserve the previous font, pagination and saved-state font;
state saving handles allocation failure without replacing the main state file.

Run `python3 simulator/test_reader_memory.py` for constrained native-heap checks:
20 complete three-chapter cycles at XS width in a 128 KiB loader-only heap, and
all four samples with changing widths in 256 KiB. The loader is compiled to MPY
for these checks. UI/framework memory and actual device latency are separate.
`python3 simulator/test_reader.py` also checks the UI, saved positions, bookmarks,
library cleanup and injected allocation failures.

That earlier allocation fix was SD-only. The buffered-reader preview above
supersedes whole-chapter pagination and supplies an optimized input adapter in
its matching UF2. Physical retesting of the sample books remains necessary.

## Large manifest fix (2026-11-03 SD preview)

The metadata loader now streams the container and package through the bounded
512-byte tokenizer. It scans the package twice: first for reading-order IDs
and the title, then for only the matching readable manifest paths. Unrelated
image/script records are not retained. Reading-order paths are pooled in one
string; the optional ZIP lookup cache is cleared before a compressed stream
allocates its window, reducing long-lived heap fragmentation. CRC/length checks
still run to completion for both metadata passes. Oversized metadata errors
include the resource name, declared size and limit.

This addresses books with manifests above the former 64 KiB limit. It does not
add MathML/table layout, more chapter images, or persistent text checkpoints.
Metadata opening remains synchronous; the two bounded passes can pause the UI
on a slow SD card. This is an SD-only update on the buffered-reader preview UF2.

`python3 tools/tests/test_reader_metadata.py` checks original manifests above
100 KiB, stored/deflated input, source/MPY loaders, index limits, duplicate/missing
IDs, CRC failures and repeated cleanup. The compiled synthetic metadata probe
passes at 160 KiB; the supplied complex textbook opens and reaches the first
page of all 39 chapters at 256 KiB in the compiled numeric/reader core. A 160 KiB
textbook probe still fails its decompression-window allocation. These figures
exclude full UI and physical SD/display costs; device retesting remains required.
The supplied textbook is not included in tests or packages.

## Device feedback and next work — 3 November 2026

User confirmed that Mechanical Engineering Design now opens on physical
PicoCalc after the metadata SD patch. This confirms the reported opening error
is resolved for that book/device; it does not qualify every chapter, image,
layout or navigation operation. Earlier cumulative checks were also reported
passing on the device.

The following are requested features, not implemented behavior:

- **Chapter/navigation utilities:** chapter list with fast selection; Go to
  chapter and Go to page. Use EPUB navigation labels/hierarchy where available,
  with a reading-order fallback. Distinguish reader/reflow page numbers from
  printed-book page labels; do not invent a fixed whole-book page number while
  pagination is incomplete.
- **Controls:** `[` = previous page, `]` = next page. In image viewing, arrows
  pan the image instead of selecting the previous/next image. Retain access to
  the image list and choose explicit separate image-selection bindings. Verify
  the actual PicoCalc bracket-key mapping before deployment.
- **Full-resolution image viewing:** preserve original source pixel detail;
  provide a 1:1 view with arrow-key panning, plus a fit view for orientation.
  The 320-pixel screen shows a viewport of a larger image. Decoding/storage must
  remain bounded: use tiles, an SD raster cache or qualified PSRAM capacity,
  rather than allocating a whole source image in the Python heap. Existing
  decoder scale/source limits need review; all chapter images must be reachable.
- **Fullscreen:** hide reading/viewer chrome to use the available display area,
  with a clear way to restore controls; preserve passage position on toggling.
- **Low-light mode** (working name): pitch-black background and reddish-gray
  text, independent of the system theme. User described this as eye-friendly/
  eyestrain prevention; treat it as a visual preference, without promising a
  medical benefit. Choose a legible text contrast and persist the preference.
- **Correct equation display — crucial priority:** preserve mathematical
  structure and symbols instead of flattening MathML to text. The supplied
  textbook contains extensive MathML, tables and MathJax resources. Investigate
  presentation-MathML conversion into the existing math layout renderer;
  preserve fractions, scripts, roots, operators, fences and equation grouping.
  Render supported expressions without evaluating them or executing EPUB
  JavaScript. Handle wide expressions through a separate pannable view and
  disclose unsupported constructs instead of silently displaying misleading
  mathematics. Equations embedded as images depend on the image-viewer work.

### Proposed implementation order

1. Audit representative equations in the supplied textbook and define a small
   supported MathML set, with original reference fixtures and visual comparisons.
   Build one equation-rendering prototype before expanding general reader UI.
2. Add chapter list/fast selection and bracket paging, then indexed persistent
   text chunks so chapter/page jumps and reopening avoid repeated full replay.
   Define page-number semantics and preserve font-independent bookmarks.
3. Integrate supported equations into pagination, allocating room for their
   actual height and preserving text/equation order and reading anchors.
4. Add full-resolution image viewport/panning and complete image selection,
   with explicit memory/disk limits and a matching UF2 if decoder changes need it.
5. Add fullscreen and low-light presentation modes, reusing the same reading
   state and navigation. Recheck equation/image contrast and font reflow.

Keep changes in small testable packages, with source/MPY checks and physical
PicoCalc retesting after each package. The order is a proposed development plan;
all requested items above remain tracked until implemented and validated.

## MathML equation prototype — 3 November 2026

Status: implemented locally, source/MPY checks and sample visual review passed;
**awaiting physical PicoCalc testing and user acceptance. This item is not ticked.**
Other requested reader features remain on hold until this prototype is accepted.

While reading an EPUB, press **F8** (Shift+F3 on PicoCalc) for a read-only
viewer of the current chapter's MathML equations, in document order. This starts
at the chapter's first equation, not the nearest equation to the current page.
`[` and `]` select the previous/next equation; arrows pan; F6 cycles equation
font sizes; F9 opens/closes viewer help; Esc cancels scanning or returns to the
exact cached text page. Earlier equations replay the bounded chapter stream.
The viewer does not change reading font, bookmarks, anchors or saved position.

The display handles rows/tokens, fractions (including Unicode quarter/half/
three-quarter forms), simultaneous sub/superscripts, square/nth roots, under/
over limits, overbars, fenced expressions, matrix/equation arrays, Greek letters
and a bounded symbol set. It uses the calculator renderer's clipping/drawing
primitives with a separate read-only MathML layout. Original 5x7 bitmap math
symbols ship in the SD app because native Spleen drawing remains ASCII-only.
Typography is simplified, including upright identifiers and stacked rendering
of bevelled fractions; mathematical grouping is retained. This is not a full
MathML engine and does not execute JavaScript or evaluate mathematical input.

Only one expression is retained, with limits of 768 nodes, 24 levels and 4,096
text characters. The XHTML tokenizer continues to bound individual tags.
Unsupported elements, semantic attributes, symbols, oversize trees or malformed
structure show a message instead of drawing a partial/flattened equation as
valid mathematics. Browsing can continue past an unsupported expression.
Alignment marks (`maligngroup`, `malignmark`) are deliberately unsupported.

The reading page itself is still the existing text-only rendering. Equations
are inspected through F8; replacing flattened text with properly sized inline/
block equations and preserving anchors is a later integration step, after
acceptance of this viewer. Image-based equations use the existing image path.
General HTML tables are not changed by MathML matrix support.

### Check on the device

Install the SD-only equation-preview package over the current buffered-reader
preview, keeping its UF2. The package includes the manifest fix and the original
**PicoReader Equation Check.epub**. Open that sample, press F8, and check:

1. Sigma with subscript x equals F over A, with a horizontal fraction bar.
2. The i subscript and 2 superscript share a base x; the square-root bar covers
   the complete a-squared plus b-squared expression.
3. The overbar covers x; the sum shows i=1 below and n above.
4. The integral limits are 0 and L, and the displayed differential occurs once.
5. Matrix columns align and brackets enclose all rows; Greek letters are distinct.
6. The wide equation pans in both directions without overwriting the header.
7. Cube-root index, theta, pi, rho, inequality and partial-derivative glyphs are
   legible at the available fonts.
8. The deliberately unsupported expression displays a message; `]` reaches
   the next valid equation. Esc preserves the reading passage and bookmarks.

Then test the supplied complex textbook. Its reader chapter 12 corresponds to
printed Chapter 1 and contains 45 MathML expressions; reader chapter 9 also has
four in its preface. Use existing F3/F4 chapter navigation and then F8. Record
reader chapter, viewer equation number, font and exact error for any problem.
Compare the mathematical grouping/symbols with the original book, including
wide expressions and matrices. Viewer equation numbers are occurrence numbers,
not the textbook's printed equation labels.

### Host verification and limits

- `python3 tools/tests/test_reader_math.py`: independent standard-library XML
  structure references; parser UTF-8/entity/self-close boundaries and malformed/
  oversized recovery; script geometry, matrix/fraction layout and clipping;
  source/MPY F8 navigation, font/help, panning, cancellation, text-page return
  and cleanup. Twelve compiled core cycles pass with a 256 KiB heap; this
  excludes the full UI and device SD/display costs.
- `simulator/audit_reader_math.py BOOK.epub [compiled-apps-directory]`, using
  desktop MicroPython: at 384 KiB compiled core heap, 2,275 of the supplied
  textbook's 2,281 MathML expressions are accepted for layout; six report
  unsupported alignment marks. This is coverage, not visual proof for every
  expression. A 256 KiB corpus probe failed a 32 KiB inflate-window allocation;
  full-device memory testing remains required.
- Original sample screenshots visually reviewed at native 320x320 resolution.
  Reader metadata, buffer/reflow/CRC, bookmarks/UI and image checks passed.
- Neither the textbook nor extracted textbook content is included in packages
  or committed tests. Original fixtures are generated with
  `python3 tools/build-reader-math-sample.py OUTPUT.epub`.

## Mixed text/equation reading preview — 3 November 2026

The user reported the F8 prototype looks good on device. This next step is
implemented locally and awaits a separate physical-device acceptance test.
EPUB reading now uses height-aware mixed text/equation pagination. Each MathML
expression, including source-inline math, receives its own block in document
order. Supported expressions that fit are drawn directly; oversized expressions
show an F8 prompt rather than silently clipping their mathematics. Unsupported
expressions retain an explicit notice. The six alignment-mark expressions from
the earlier prototype remain unsupported.

Press Tab to select an equation on the page (small accent tick at its left),
then F8 to open that expression in the existing pannable viewer. Esc returns
to the same cached reading page. With no page equation, F8 retains chapter
browsing. Text is split around equations; this is not yet same-line math flow.
General HTML tables and image handling are unchanged.

Equation trees are kept in a private append-only SD cache, at most 32 KiB per
record and 16 MiB per session; it contains no growing in-memory equation index.
Page payloads hold small references, remaining within the existing bounded
RAM/SD page caches. Font reflow temporarily owns a separate cache. These files
are removed on normal exit; if the equation cache fills, reopen the book.
The SD must be writable. Equation creation/layout is cooperative between input
chunks and expressions; individual bounded layout/serialization calls are atomic.

Normalized visible-character anchors continue counting the original MathML
text even though it is no longer displayed flattened. Existing saved passage
and bookmark offsets remain valid. Page-count layout version is bumped to 3,
so old page totals rebuild under the new layout; page numbers may change.
TXT and direct legacy text pagination retain their prior implementation.

Validation: simulator/test_reader_inline.py checks all nine original equation
blocks in order, height budgets, old final character offsets, contextual F8,
font reflow, bookmarks/reopening, disk page replay and cache cleanup, on source
and compiled code. Legacy streaming passes its existing compiled 160 KiB core
check. A compiled 384 KiB core probe reached 32 mixed pages in four textbook
chapters with 14 supported equation blocks; full UI/device costs are excluded.
Reader UI, metadata and image regression checks also pass. Physical acceptance
is pending. Test the original Equation Check sample first, then the textbook;
report reader chapter/page, equation number, font and exact error or overlap.

## Chapter navigation preview — 3 November 2026

User reports the mixed text/equation pages passed on-device tests. That step is
accepted as a checkpoint. The following navigation update is implemented and
host-checked, but awaits separate physical acceptance.

- **F10 (Shift+F5):** chapter list. Up/Down selects, Left/Right moves ten
  entries, Enter opens the selected chapter at its beginning.
- **F1 in that list:** Go to chapter. Typing digits from the list also opens
  chapter-number entry. Enter confirms; zero and numbers beyond the chapter
  count are rejected.
- **F2 in that list:** Go to page within the current reading chapter and font.
  This uses reflowed reader pages, not printed book labels or a whole-book
  fixed page number. Known out-of-range pages are rejected. For an uncounted
  chapter, an oversized jump scans to its end and shows the last page with a
  notice, never silently entering the following chapter.
- **Esc:** closes help, then cancels number entry to the chapter list, then
  returns from that list to the unchanged reading passage. F9 opens menu help.
- **`[` / `]` while reading:** previous/next page. Equation-view bracket
  bindings keep their existing meaning inside that viewer.

Titles load cooperatively from EPUB2 NCX or EPUB3 toc navigation resources;
only the first title for each reading-order document is kept. Subsection
fragments are not separate destinations in this chapter list. At most 16 KiB
of title characters are retained, with filenames as fallbacks. TXT displays
its bounded parts as chapters. Optional missing/damaged TOC metadata leaves
chapter selection available. The currently displayed chapter numbering still
follows spine order, including front matter.

A jump outside cached pages can still replay text from the chapter start.
Persistent indexed text chunks remain the next work item after device testing.
Esc during loading retains the existing return-to-library behavior. Metadata
label discovery uses small work batches; keys remain available while loading.

Validation: tools/tests/test_reader_navigation.py covers independent original
EPUB2/EPUB3 fixtures, chapter labels, numeric and list selection, help/cancel,
range checks, bracket turns, chapter-confined oversized page jumps, title
fallbacks, TXT and exit cleanup, on source and freshly compiled apps. The
textbook yields titles for all 39 reading-order chapters in a 384 KiB compiled
core probe (excluding full UI/device memory). Mixed-equation, reader lifecycle
and metadata checks passed. Device acceptance remains pending.
