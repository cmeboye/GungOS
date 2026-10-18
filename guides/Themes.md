# Theme colours

Open **System → Settings → Theme Color**. The dark canvas is fixed; the accent
colours the category/footer bars, selections and themed application controls.
The top status bar stays black with white text.

- **Arrow keys:** browse 30 colour swatches. The name and display hex value appear
  below the grid, with a live preview of text and a selected control.
- **F2:** enter a custom RGB colour as six hex digits (`RRGGBB`, optional `#`).
  Typing the first digit replaces the prefilled value. Left/Right move the cursor;
  Back and Del both erase before it. Enter previews the completed colour; Esc
  discards the edit and returns to the swatches.
- **Enter on the swatch screen:** save and return to Settings.
- **Esc on the swatch screen:** return without saving.

Previewing does not change the active system theme or write to the SD card.
Saving updates the existing integer `theme_color` in
`picoware/settings/picoware.json`, preserving Wi-Fi credentials and other settings.
A failed save leaves the picker open with an error; fix the SD issue and press
Enter to retry, or Esc to cancel. The saved colour is restored at startup.

The display uses RGB565 (65,536 colours), so custom RGB888 values are rounded to
the nearest supported colour. The preview's hex value shows the actual display
colour; for example, `#D48844` becomes `#D68A42`. Text on solid accent backgrounds
switches between black and white for readability.

The picker is firmware code and needs a new UF2 to install on a physical Pico.
After that, choosing or saving another colour does not need reflashing. The
simulator uses the updated source immediately.
