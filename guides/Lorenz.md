# Lorenz screensaver and widget

Open **Apps → Misc → Screensavers → Lorenz** for the full-screen view.
To use it on the desktop, choose Lorenz under **System → Settings → Screensaver**.
Press **F3** on the desktop to give the widget keyboard focus.

## Controls

- **F2:** open settings. Animation pauses while the settings panel is open.
- **Space:** pause/resume the animation.
- **F4:** show/hide performance stats for this session. To retain that choice,
  open settings and save. F1 remains the firmware's screenshot shortcut outside
  the desktop.
- **F5:** reset the trajectory, retaining the current quality settings.
- **Esc:** leave the screensaver or return focus from the widget. Inside settings,
  Esc discards the pending edits and resumes the previous animation.

In settings, Up/Down select a row and Left/Right change its value. Enter also
cycles a value; **F2 saves and applies**, or select **Apply & save** and press Enter.
Defaults only resets the pending fields; save to apply or Esc to discard them.

## Quality settings

| Setting | Choices | Default |
| --- | --- | --- |
| Detail | Coarse /12, Medium /6, Balanced /4, Smooth /3, Fine /2, Ultra /1 | Smooth /3 |
| Trail | 192, 384, 768, 1536, 3072, 6144 points | 768 |
| Target refresh | 4, 8, 12, 16, 24, 30 FPS | 8 |
| Stats | On/off | On |

Detail is the number of numerical integration steps between retained points.
Lower values draw smoother curves. Increasing only the trail capacity keeps more
history; it does not increase point density. The panel estimates trail memory and
duration at the target speed. The default uses 3 KiB for roughly six seconds of
trail; 6144 points use 24 KiB. Trajectories reset when detail or capacity changes.

There are 384 midpoint integration steps per second at the target refresh rate,
with the original fixed mathematical step (`dt = 0.006`). Changing FPS changes the
number of steps per frame to keep the animation speed consistent. Work is bounded
to 96 integration steps and 6143 line segments per frame. Under load the animation
slows instead of building an unbounded catch-up queue.

The desktop widget uses the available native square (238 × 238 in the compact
layout preview; 184 × 184 in the previous v1.0 layout). Its host caps updates at 8 FPS. Lorenz
shows this cap and uses it for animation pacing even if a higher target is saved.
Use the full-screen app to experiment with higher refresh rates without a UF2
change.

## Performance readout

The overlay shows measured/target FPS and the previous frame's **work** time:
numerical integration plus drawing, measured before display submission. FPS is
measured between updates, so it also reflects scheduling/display overhead.
`SLOW` appears when frame execution exceeds its budget or the measured refresh
rate falls below 85% of the effective target. For a widget, the work timer excludes
the desktop's later composition; measured FPS still includes that delay.

The simulator runs native code on the host computer. Its timings, including
`pico2w` speed mode, do not predict physical Pico execution speed. Check on-device
FPS, work time and keyboard responsiveness before retaining demanding settings.
The panel warns for trails above 1536 points. Low-memory allocations and SD-save
failures leave the current animation/options intact; reduce the trail or retry.

Settings save only on confirmation, inside the `lorenz` object in
`picoware/settings/picoware.json`. Saving preserves other device/Wi-Fi settings.
Invalid saved fields fall back to defaults. If a large saved allocation fails at
startup, the demo falls back to 192 points at 4 FPS without overwriting that file.

This is an SD application update and needs no new UF2. This review changes source
and simulator previews only; the compiled SD release bundle is deliberately left
untouched until visual feedback is complete.
