# Engineering desktop

The 320 × 320 home screen uses the supplied dark-mode logo artwork.
Dark mode is fixed; legacy light-mode preferences are ignored. The logo sits
at the top left, system information at the top right, menu items at the bottom
left and a square 184 × 184 widget area at the bottom right.

The Apps category lists **PicoDESK, PicoLAB, Games, Misc**. PicoDESK contains
Eggcel, PicoWord and PicoPaint. PicoLAB contains Graph, Graph3D and engineering
tools. Screensavers are under Misc. System menus use the same theme/layout as
the application launchers. These changes require the v2.2 UF2; the simulator
previews them before a build. The home geometry remains unchanged in v2.2.

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

The footer shows only `H: Help   I: Info`. The help panel describes the desktop
controls. Info is also available through **System → About**; Up/Down scrolls
its text and Escape returns. While a widget has keyboard focus,
letters go to that widget; use F1 to return to desktop controls.

## System information

The panel displays the board, current clock frequency, and free/used/total
resource counters with percentage free. Compact values use binary K/M/G units;
scroll down with F1 and the arrows for exact byte counts.

- Heap measures MicroPython allocations and its available allocation region.
- Flash measures the internal **filesystem**, rather than the whole firmware
  partition or physical flash chip.
- PSRAM reports external memory when the board exposes those counters.
- SRAM reports physical internal capacity: 520 KiB for Pico 2 boards and
  264 KiB for Pico boards. Whole-chip free/used accounting is unavailable and
  appears as `-`. The Python heap overlaps SRAM, so these rows are not additive.

Counters refresh when entering the information panel and every five seconds
while focused. The desktop simulator reports host heap and host filesystem
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
To draw directly at the available box size, declare:

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

The desktop changes are firmware source changes and need the v2.2 UF2 build
for the physical device. Copying the engineering SD bundle alone does not
update the home screen. The current UF2 is left in place until that build.
