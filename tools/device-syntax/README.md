Stubs for `tools/check-device-syntax.sh`: a minimal C library (`libc`), the few
MicroPython declarations the display code needs (`stub/py`), and the two
headers the pico-sdk normally generates at build time (`gen/pico`). They exist
only so device code can be type-checked on a Mac without the Arm toolchain.
