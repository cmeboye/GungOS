# Shared PSRAM lifetime regression

Run `sh src/MicroPython/PicoCalc/picoware_psram/tests/run-tests.sh` from the
project tree. It compiles the unmodified device C binding into host MicroPython.
Only QSPI transfers use an in-memory chip stub. It checks that another interface
and repeated system-counter reads preserve live allocations, that collecting an
interface keeps the bus ready, and that the reserved display bytes survive.
This does not test electrical timing or the physical LCD.
