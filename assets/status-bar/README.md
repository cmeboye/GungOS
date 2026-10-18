# Desktop status artwork

Original full-colour Wi-Fi/Bluetooth PNGs supplied for GungOS are used at their
native 12 × 12 size, retaining colours and transparency. Both desktop bars are
16 pixels high. Battery level is displayed as an exact text percentage (`--%`
when unavailable); no battery artwork is bundled.

The compiler maps `notconnected` filenames to the internal `disconnected` state.

With Pillow installed, regenerate/check the compact firmware module using:

```sh
python3 tools/compile-status-icons.py
python3 tools/compile-status-icons.py --check
```

The device does not need a PNG decoder or SD copies of these images. The generated
`src/MicroPython/picoware/assets/status_icons.py` is frozen with the firmware, so
installing changed artwork on the Pico requires a new UF2. The simulator reads
that generated source on its next launch.

Capture all 20 battery/link combinations, four accent themes, and three
review sheets using the native simulator renderer:

```sh
python3 tools/capture-status-previews.py
```

Screenshots are saved under ignored `verification/status-bar/`. Captures use
explicit synthetic battery/connection states, not a physical connected device.
The live desktop shows reported state; drawing the BT indicator never starts a
Bluetooth controller or simulates a persistent connection. Current Bluetooth
tools still close their controller when exited.

The top status bar stays black across accent choices, with white clock and battery
percentage text. Wi-Fi/Bluetooth artwork retains its supplied colours. Category
and footer bars retain the selected accent and automatic black/white text contrast.

Only two composited icon buffers are cached at once (784 bytes of pixel data), and battery
hardware is sampled once per second. On the host, the simulator control file
`sim_frame.rgb565.control` accepts `battery 25` and `charging on`/`charging off`
lines to preview changes while the desktop is open.
