# Menu logos and paths

Maintained GungOS menus use the small GungOS logo followed by `/ Menu name`.
PicoDESK and PicoLAB use their custom logos for their own menus and nested
selectors. The Pico brands retain the system accent colour.

The shared renderer is `picoware.gui.style.header()`. Standard Menu and Choice
widgets inherit it; category navigation, theme/date selectors, screensaver
selection and the file browser use it too. File-browser options, context menus,
confirmations and name-entry dialogs keep their parent brand. The CSV picker
opened by Eggcel therefore shows the PicoDESK logo and an Eggcel/import path.

Bundled SD apps use the same renderer through `engtools.ui.theme.header()`:
PicoWord/PicoPaint menus, Eggcel menus and charts, Lorenz settings and Tetris.
PicoLAB keeps its scoped hierarchy; graph settings append their current page.
The calculator/Beam/PicoDESK layouts reuse their existing 18-pixel strip;
ordinary list menus retain the 23-pixel header. Long paths use the smallest
font, then shorten the parent portion to keep the current item visible.
No extra framebuffer or global logo override is used.

The main dashboard keeps its separate large-logo layout. Arbitrary third-party
SD apps can draw their own menus; they should use this API to follow the same
convention. Working graph/canvas areas are not replaced with menu overlays.

Installing the native menu fixes requires a new UF2. Update the SD applications
and the complete `engtools`/`desktopapps` packages together for their menu
changes. Those SD apps include a compact header fallback so they still open
on existing UF2 versions before that firmware update is flashed.

Validation:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_menu_headers.py
```

This records the logo and path actually drawn by native menus/selectors and
bundled app menus, checks bounds and brand restoration, exercises the old-UF2
fallback, and saves screenshots to `/private/tmp/gungos-menu-header-previews`.
The navigation, theme, PicoDESK, CSV-import, calculator/PicoLAB, Lorenz and Tetris
regressions cover their existing controls and data behavior. These are simulator
checks; physical display review happens with the next firmware build.
