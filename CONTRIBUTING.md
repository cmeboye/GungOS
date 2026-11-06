# Contributing

GungOS targets PicoCalc with Raspberry Pi Pico 2 W. This branch is unreleased
1.36-dev; keep the existing v1.35 tag and packages tied to their original source.

Application source is under `builds/MicroPython/apps_unfrozen/`; shared engineering
code belongs in `engtools`, desktop apps in `desktopapps`. Firmware and native
modules live in `src/MicroPython/`. Record upstream revisions and local changes
when editing bundled dependencies; preserve their notices.

Follow the system theme and [PicoLAB keys](guides/Keys.md). Escape closes the
innermost help/edit/view; Back/Del erase before the cursor. Help preserves drafts,
selection and focus. Keep work bounded for Pico 2 W memory and preserve unsaved
documents when an operation fails.

Use the pinned dependencies and build instructions in [BUILD.md](BUILD.md).
Before submitting changes, run the same source checks as GitHub Actions:

```sh
python3 tools/check-source.py --build
```

After a successful build, `python3 tools/check-source.py` reuses the matching
compiler/simulator. Logs and the step summary are in `.build/source-checks/`.
Fixture drivers generate original books/images/reference data; source validation
does not require device data, personal books or optional audio recordings.

Never add device credentials, user documents, local SD/flash trees, build
intermediates or unlicensed recordings. Run `python3 tools/check-public-repo.py`
before committing. Release archives belong with a matching source revision and
notices. Hardware performance/compatibility claims require physical-device checks.
