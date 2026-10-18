# Engineering desktop

The 320 × 320 home screen uses the supplied dark-mode logo artwork.
Dark mode is fixed; legacy light-mode preferences are ignored. The logo sits
at the top left, system information at the top right, menu items at the bottom
left and a taller widget panel at the bottom right. Its native widget surface is
a square 238 × 238 pixels, filling its frame without a separate caption strip.

The Apps category lists **PicoDESK, PicoLAB, Games, Misc**. PicoDESK contains
Eggcel, PicoWord and PicoPaint. PicoLAB contains Graph, Graph3D and engineering
tools. Screensavers are under Misc. System menus use the same theme/layout as
the application launchers. The compact layout below ships with v1.1; installing it on the device requires
the matching UF2 and SD app update. Previous local packages are preserved for
rollback.

| Area | Position (x, y) | Size (width × height) |
| --- | --- | --- |
| Status bar | 0, 0 | 320 × 16 |
| Logo | 8, 20 | 78 × 20 |
| System summary | 93, 17 | 226 × 25 |
| Category bar | 1, 43 | 318 × 18 |
| Menu panel | 1, 62 | 77 × 240 |
| Widget panel | 79, 62 | 240 × 240 |
| Native widget surface | 80, 63 | 238 × 238 |
| Help / Info footer | 1, 303 | 318 × 16 |

Coordinates count pixels from the top left. Panel sizes include their one-pixel
outlines. The native widget fills the square interior. Menu items always use the
smallest font; longer names wrap at word boundaries to remain readable. The logo is packed from `assets/gungOS_logo_large.png` without resizing, using
`python3 tools/convert-dashboard-assets.py` (`--check` verifies the result). The
large source artwork keeps its native resolution and is centered between the
left edge and system summary, one pixel above its source position. Category/footer bars and body panels
have a one-pixel outer margin; a one-pixel gap separates the menu, widget and
bars. The small alternative is kept in `assets/gungOS_logo_small.png`.

## Navigation

| Key | Action on the desktop |
|---|---|
| Left / Right | Select Apps, System, Comms or Utils |
| Up / Down | Select an item in the current category |
| Enter | Open the selected item |
| Escape | Return from a panel; on the main menu, reset to Apps |
| H | Show or close help |
| I | Open GungOS version, features and credits |
| F1 | Focus system information; Up / Down scroll; F1 or Escape returns |
| F3 | Focus the selected widget |

Back and Del both erase before the cursor and never navigate away.
F6–F10 require Shift+F1–F5 on the PicoCalc.

Opening a full-screen app and returning preserves the menu selection. Alt+S
saves a screenshot to `screenshot.bmp` on the SD card from any screen; the key
is not passed to the app. F1 and the other function keys belong to the app.

The top status bar is black, with white time and battery-percentage text and the
supplied connection icons. Category and footer bars use the selected accent.

The footer shows `H: Help   I: Info` at the left and the firmware version at the
right. The help panel describes the desktop
controls. Info is also available through **System → About**; Up/Down scrolls
its text and Escape returns. While a widget has keyboard focus,
letters go to that widget; use F1 to return to desktop controls.

## System information

The compact header shows board/frequency and three usage bars: H = Python heap,
P = external PSRAM, SD = card filesystem. Bar labels show percentage **used**;
unknown counters show `--` with an empty outlined bar.

F1 opens a larger resource overlay with free/used/total counters and percentage
free. Compact values use binary K/M/G units; Up/Down scrolls to exact byte counts.

- Heap measures MicroPython allocations and its available allocation region.
- Flash measures the internal **filesystem**, rather than the whole firmware
  partition or physical flash chip.
- SD reports the card filesystem through the SD storage driver.
- PSRAM reports external memory when the board exposes those counters.
- SRAM reports physical internal capacity: 520 KiB for Pico 2 boards and
  264 KiB for Pico boards. Whole-chip free/used accounting is unavailable and
  appears as `-`. The Python heap overlaps SRAM, so these rows are not additive.

Counters refresh on entry, when opening the information overlay, and every five
seconds on the desktop. The desktop simulator reports host heap and host filesystem
space; it does not predict memory use on the Pico.

## Screensaver / widget selection

Open **System → Settings → Screensaver**. Choose **None** to leave Box 3 empty
(the default), or select a `.py` / `.mpy` app from
`picoware/apps/misc/screensavers` (legacy `picoware/apps/screensavers` also works) on the SD card. Enter saves the selection in
`picoware/settings/picoware.json`, under the `screensaver` key. A failed write
keeps the selector open and reports the failure.

The widget runs with an offscreen drawing surface, separate input and a local
view stack. F3 enters it without sending the focus key to the app. Subsequent
keys go to the widget, including F3 for calculator Options. The app's Escape
action releases focus; F1 can also return control to the desktop information
panel. While unfocused, the widget continues updating without receiving keys.

Opening a full-screen app stops the widget to release its memory. Returning to
the desktop restarts it; widget session state is not retained across that move.

## Writing widgets

Use the standard Picoware `start(vm)`, `run(vm)` and `stop(vm)` entry points.
To draw directly at the available square surface size (currently 238 × 238), declare:

```python
WIDGET_NATIVE = True

def start(vm):
    vm.draw.erase()
    vm.draw._text(8, 8, 'My widget', vm.foreground_color, 0)
    vm.draw.swap()
    return True

def run(vm):
    from picoware.system.buttons import BUTTON_BACK, BUTTON_ESCAPE
    if vm.button in (BUTTON_BACK, BUTTON_ESCAPE):
        vm.back()

def stop(vm):
    pass
```

Read `vm.draw.size` for the current dimensions. Existing apps default to a
virtual 320 × 320 surface. A module can instead declare
`WIDGET_SIZE = (width, height)`. The desktop scales that surface to fit the
square, preserving aspect ratio and centring it. Text in a scaled full-screen
app is smaller; native-size widgets should arrange their UI for the box.

The surface uses one byte per pixel with RGB332 colour. Basic Picoware drawing,
text, bitmaps and nested views are supported. Updates are capped at eight per
second when idle; focused key events run immediately. Dimensions must be at
least 16 pixels per side, with at most 102,400 pixels total. Allocation also
requires an 80 KiB heap reserve; this is an initial check, not a guarantee that
the app's later allocations will fit.

Arbitrary apps are not universally compatible: direct hardware drawing,
LVGL, JPEG/alpha drawing and unsupported view-manager APIs cannot be adapted
by this wrapper. Blocking app code can still stall the desktop. Unsupported
operations or app exceptions stop the widget and display an error in its box.

`Calculator Widget.py` is a native-size Calculate interface with no history,
using the shared scientific editor and evaluator. Its `.mpy` is packaged in
`builds/MicroPython/engineering-preview.zip` alongside the shared `engtools`
modules. The full-screen calculator remains available through PicoLAB.

## Preview and firmware

```sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w \
  --network offline --audio silent
```

The desktop changes are firmware source changes and need the v1.1 UF2 build
for the physical device. Copying the engineering SD bundle alone does not
update the home screen. The current UF2 is left in place until that build.
