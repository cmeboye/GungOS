# Appearance

Open **System → Settings → Appearance** to edit four shared colour roles:

| Setting | Default | Used for |
| --- | --- | --- |
| Accent color | Blue | Selections, highlights, themed controls and plots |
| Background color | Black | Main canvas, status bar and widget surfaces |
| Text on dark | White | Text on dark canvases and solid controls |
| Text on light | Black | Text on bright canvases and solid controls |

The system chooses the text role from the brightness of the surface. Panel,
grid and muted colours are derived from the canvas and text. Logos composite
over their surface; white lettering uses its text role. Decorative logo colours,
radio artwork, document colours, game pieces and error colours retain their
meaning. Changing the appearance does not recolour a saved painting or document.

Use Up/Down to choose a role and Enter to edit it. The colour picker offers
32 swatches, including black and white. **F2** opens a custom `RRGGBB` hex editor
with an optional `#`. The first typed digit replaces the existing value;
Left/Right move the caret, and Back/Del both erase before it. Enter accepts a
complete hex value; Esc discards that hex edit.

Enter on the swatch screen sets the colour in the appearance draft. Esc returns
without changing that role. The preview combines the draft canvas, accent and
both text colours, with contrast ratios for normal text and a selected control.
A low-contrast label indicates a ratio below 4.5. The controls retain a readable
palette even when the draft text would be invisible.

**F1 Save** on the Appearance page saves all four roles together and applies them
immediately. **Esc** cancels the entire draft. **F2 Reset**, or the Reset appearance
row, loads the defaults into the draft; F1 is still needed to save the reset.
Browsing and previewing never write settings or alter the active appearance.
A failed save leaves the draft open; correct the SD issue and press F1 to retry.

Values are stored as RGB565 integers in `picoware/settings/picoware.json` under
`theme_color`, `background_color`, `text_on_dark` and `text_on_light`. Existing
cards keep their accent and use the defaults for missing fields. The save keeps
other preferences and Wi-Fi settings. Colours are restored at startup.

The current framebuffer reduces colours to **RGB332 (256 colours)**. Hex input
is stored at RGB565 precision, and the preview shows the same quantization as
the screen. Nearby hex values may look identical. Contrast and surface brightness
are measured after that reduction.

The settings UI and shared firmware theme code require a new UF2 on the Pico,
with the accompanying SD app update for the calculator and other app changes.
Choosing or saving another appearance after installing it requires no reflash.
The simulator uses the updated source immediately.
