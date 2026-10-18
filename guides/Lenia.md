# Lenia screensaver and widget

Open **Apps → Misc → Screensavers → Lenia** for the standalone view. Choose
**System → Settings → Screensaver → Lenia** for the desktop widget. Both use
one SD entry point that reads its actual drawing dimensions; the widget renders
natively at 238 × 238 rather than shrinking a full-screen interface. F3 on the
desktop gives it keyboard focus; subsequent F3 presses go to Lenia's Random action.

The widget fills the square supplied by the desktop, including a 220 × 220
surface if that is provided. It has no inner plot frame or branded header:
Lenia appears at the top left, measured Hz/compute ms/generation at the top
right, species and parameters at the bottom left, and F9 Help at the bottom
right. Compact text overlays keep the field square without a separate inset.
Crossing any edge wraps the organism onto the opposite edge; there are no
bounding walls. The standalone app retains its framed plot and branded header.

## Controls

| Key | Action |
|---|---|
| F2 | Settings; animation stops while menus are open |
| F3 | Randomize the configured seed's position/orientation; Noise gets new values |
| F4 | Toggle performance statistics for this session |
| F5 | Restart the configured seed |
| Space / P | Pause or resume |
| N | Advance one generation while paused |
| F9 | Scrollable help with controls and parameter explanations |
| Esc | Return from help/settings; leave standalone view or release widget focus |

Random and Reset retain the active rule parameters and pause state. There is no
automatic reseeding: extinction, oscillation or saturation remain visible. For
an empty field, F5 retries the seed; Settings → Defaults restores Orbium rules.

Settings use Up/Down to select and Left/Right to adjust. Enter opens numeric
entry or cycles a choice. Type to replace a prefilled number, or use arrows to
edit it; Back and Del erase before the cursor. Enter commits an entry; Esc
cancels it. In the settings list, Esc discards unapplied changes.

**F2 applies and saves.** **Apply this session** changes only the current run.
**Random rules** (also F3 inside Settings) changes the draft's growth parameters
and kernel radius in a bounded range, retaining grid size and target speed.
Apply to try those rules; viable organisms are not guaranteed.

## Editable parameters

| Group | Parameter | Supported values |
|---|---|---|
| Simulation | Grid | 16 × 16, 32 × 32, 64 × 64; default 32 × 32 |
| Simulation | Target steps/s | 1, 2, 4, 8, 12, 16; default 8; widget maximum 8 |
| Simulation | Time step dt | 0.01–0.30; default 0.10 |
| Growth | Centre mu | 0.01–0.60; default 0.15 |
| Growth | Width sigma | 0.001–0.15; default 0.015 |
| Growth | Shape | Gaussian, Polynomial, Step |
| Kernel | Radius R | 2–31 grid cells, also limited to grid/2 − 1; default 8 |
| Kernel | Shape | Polynomial, Gaussian, Step |
| Kernel | Centre / width | 0.10–0.90 / 0.05–0.50 within each ring |
| Kernel | Rings | 1–3 concentric rings |
| Kernel | Weights b1, b2, b3 | 0–1; at least one active weight must be nonzero |
| Seed | Pattern | Orbium, Twin Orbium, Ring, Noise |
| Seed | Noise density | 0.05–1; used only by Noise |
| Seed | Amplitude | 0.10–1; used by every seed |
| Display | Gamma | 0.25–2; controls brightness without changing the field |
| Display | Grid lines / statistics | On/off |

Kernel, growth and seed parameters can be entered directly within their bounds.
The kernel is normalized after weighting its rings. A too-narrow profile that
hits no grid points is rejected without replacing the live field. Inactive b2/b3
weights are retained for use when their rings are enabled. Changing grid size
clamps the pending radius to its new bound.

Grid/seed changes restart the field. Growth and kernel changes at the same grid
retain the last complete generation. Display/speed changes also retain it.
Changing arbitrary parameters can destabilize the organism; Defaults restores
the original single-ring rule configuration used by this demo.

## Numerics and performance

This is a single-channel, single-kernel Lenia implementation with periodic
edges. It uses circular convolution and the update
`A_next = clip(A + dt * growth(K * A), 0, 1)`. The Gaussian growth is
`2 * exp(-0.5 * ((density - mu) / sigma)^2) - 1`. The default kernel is a
compact polynomial ring. Multi-channel Lenia, Flow Lenia and GPU simulation
are outside this version.

The configured native ulab provides one-dimensional real/imaginary FFTs. The
SD engine composes them over rows and strided columns, caches the real spectrum
of the symmetric kernel, and performs growth/clipping with native array
operations. A comparison against direct convolution tests normalization,
wraparound and growth. The 32 × 32 Orbium preset remains alive for 400 tested
generations without automatic resets; this is not a guarantee for modified rules.

Each update yields between row/column transforms and growth rows, returning to
the host after approximately 6 ms of compute or 256 batches. A single transform
is not interruptible. One generation maximum starts per call, and slow devices
do not accumulate a catch-up queue. Only complete generations are published;
pause, reset or settings changes can discard partial work safely.

Four float32 grids use **4 KiB / 16 KiB / 64 KiB** at 16/32/64, plus FFT/growth
row temporaries, Python objects, UI and the existing framebuffer. Grid/kernel
replacement temporarily retains the previous grids for recovery. Allocation
checks preserve a reserve; failures leave current settings and the field
intact. A bad saved kernel or failed startup allocation falls back to a small
16 × 16 demo without overwriting the saved configuration.

Drawing groups adjacent cells of the same quantized density into rectangles;
it uses the actual view dimensions and system theme without another screen
buffer. The widget host owns its existing RGB332 surface and 8 Hz scheduling.
Standalone mode borrows the native SRAM screen when available and returns it
through the view lifecycle. Rendering is separate from the 6 ms compute budget.

Statistics show measured generations/second, the effective target, compute
milliseconds for the last complete generation and generation count. Compute
time excludes drawing and display composition; measured update rate includes
scheduling and drawing delays. The simulator's host timings do not predict Pico
speed. On-device testing must establish comfortable grid/rate settings.

Settings save under `lenia` in `picoware/settings/picoware.json`, preserving
other preferences. SD write verification and allocation happen before live
options are replaced. No writes occur during animation/random/reset; unsaved
session changes disappear when the widget/app is restarted.

## Installation and tests

Update `misc/screensavers/Lenia.mpy` and the complete `engtools` package together,
including `system/lenia.mpy`. The current GungOS ulab configuration is sufficient;
no new native numerical module is needed. The standalone screensaver menu's
allowlist gains Lenia in the next UF2; existing firmware can discover the new
SD file through its widget selector. The simulator uses the updated allowlist.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_lenia.py
```

Tests cover the FFT against direct convolution, live Orbium evolution, atomic
cancellation, parameter validation, menus, verified saving/recovery, pause and
single-step, random/reset, desktop focus and standalone cleanup. Preview images
are written to `/private/tmp/gungos-lenia-previews`.

## Attribution

Lenia and the Orbium unicaudatus (O2u) seed/parameters are by Bert Chan.
The numeric seed comes from the original
[Lenia dataset](https://github.com/Chakazul/Lenia/blob/master/Python/animals.json)
under the [preserved MIT license](Lenia-LICENSE.txt). The retrieved dataset's
SHA256 is `09cf0a831c1ef8a73ebfaa9126257fbe076108362b706a98d88650ca9848d206`.
The solver, UI and widget integration here are GungOS code. The preset notice
ships alongside Lenia in SD packages. See the [original project](https://chakazul.github.io/lenia.html)
for its research, demonstrations and other implementations.
