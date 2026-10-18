# Contributing

Keep application changes under `builds/MicroPython/apps_unfrozen/`; shared
engineering code belongs in `engtools`, desktop apps in `desktopapps`. Firmware
and native modules live under `src/MicroPython/`. Avoid editing pinned `vendor/`
code without recording the upstream revision and any local patch.

Use the selected system theme, Escape to return, and Back/Del as backspace.
Prefer F1–F5 for common actions. Keep work bounded for Pico 2 W memory and preserve
unsaved documents when an operation fails. Simulator results need physical-device
checks before making hardware performance claims.

Build/check instructions are in `BUILD.md`. Relevant checks include:

```sh
python3 tools/check-public-repo.py
python3 tools/check-service-independence.py
python3 tools/tests/test_public_repo.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_eggcel_revision.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_tetris_audio.py
```

The audio check generates its own test waveforms. Never add device credentials,
user documents, local SD trees, build intermediates or unlicensed recordings.
Keep upstream copyright notices and third-party license files. Build archives
belong with a release and its matching source revision.
