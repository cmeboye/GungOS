# GungOS v1.35 device-test release — 3 November 2026

Target: **PicoCalc with Raspberry Pi Pico 2 W**. Firmware and SD applications
must be installed as a matching set. Physical qualification is pending.

## Files

The local `releases/v1.35/` folder contains:

- `GungOS-v1.35-PicoCalc-Pico2W.uf2`: matching firmware, including Spleen fonts.
- `GungOS-v1.35-Clean-SD.zip`: full SD contents with clean default settings,
  every shipped app, dictionary data and three original EPUBs plus one TXT sample.
- `GungOS-v1.35-Apps-Update.zip`: applications and dictionary data for an existing
  card; excludes user settings/documents and the reader sample library.
- `GungOS-v1.35-Source.zip`: matching source, pinned dependencies, build inputs,
  firmware, SD contents and current verification reports.
- `SHA256SUMS.txt`: checksums of the downloadable artifacts.
- `README.md`: source revision, installation and validation summary.

The full SD includes 58,243 English→Italian and 50,883 Italian→English dictionary
entries. Data attribution, license and hashes are in `picoware/dictionary/`.
Optional Tetris recordings are omitted; the game is playable without them.

## Install

1. Back up your existing SD card and documents.
2. Fresh card: extract **Clean-SD.zip** directly onto a writable FAT32 SD root.
   `picoware/` must be at the root, without an extra ZIP-name folder.
3. Existing card: merge **Apps-Update.zip** onto the root, replacing matching
   application files. Retain your settings and documents. Remove stale `.py`
   copies of modules now supplied as `.mpy`, so only one copy of each is installed.
   The full SD's sample library can be copied separately if desired.
4. Put the **Pico 2 W** into BOOTSEL mode and copy the v1.35 UF2 onto its
   bootloader drive. This firmware is for Pico 2 W, not the original Pico W.
5. Insert the prepared SD and restart. Confirm v1.35 under System → Info.

## Device checks

- [ ] Boot, version, Spleen text legibility, theme and keyboard mapping.
- [ ] Open/close PicoLAB and PicoDESK repeatedly; check available heap and errors.
- [ ] Calculator: type `sum()` then Space; fill 1, Tab, 10, Tab, `k^` then
  Space and 2. F6 calculates **385**. Check the index/limits/power render, and
  history recall retains editable slots.
- [ ] `prod(k,1,5,k)` gives **120**; Space after the filled form renders Π.
- [ ] F9 help opens/closes without losing a partial expression. On PicoCalc,
  F6–F10 are Shift+F1–F5.
- [ ] Solver: `1e-12*(x-3)=0` with bounds −10..10 converges near **3**;
  `1e-12=0` reports an error instead of a false root.
- [ ] Complex mode: `1e-8*i` retains the small imaginary result on screen.
- [ ] PicoDict: `apple` → `mela`, switch direction, check responsiveness and
  missing-word behavior using the supplied SD data.
- [ ] PicoReader: open the sample EPUB/TXT books; change fonts, turn pages,
  add a bookmark, leave/reopen and reboot to check position/bookmark persistence.
- [ ] PicoCAD under Modules → Machine design; engineering help, editing and
  F6 calculation controls; 2D/3D Grapher navigation.

See [CalculatorReview.md](CalculatorReview.md) for remaining calculator work.
Complex inverse trig, difficult/repeated polynomial roots, narrow-feature
integration, extended scientific functions and asynchronous reductions are not
resolved by this release. Host checks do not establish device speed or free heap.
