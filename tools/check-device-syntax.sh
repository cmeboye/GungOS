#!/bin/sh
# Type-check device-only C files for the Pico 2 W without the Arm toolchain.
#
# Compiles with clang's Arm backend (-fsyntax-only) against the real pico-sdk
# headers in vendor/, with small stubs for the C library and MicroPython
# (tools/device-syntax). It catches missing headers, wrong SDK calls and type
# errors before a firmware build; it does not link or produce a UF2.
#
# usage: sh tools/check-device-syntax.sh [file.c ...]   (default: display files)
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
sdk="$root/vendor/micropython/lib/pico-sdk"
mp="$root/src/MicroPython"
stubs="$root/tools/device-syntax"
if [ "$#" -eq 0 ]; then
    set -- "$mp/PicoCalc/picoware_lcd/lcd.c" "$mp/PicoCalc/picoware_lcd/picoware_lcd.c" \
        "$mp/gfx/gfx.c" "$mp/gfx/gfx_lcd.c" "$mp/gfx/gfx_mesh.c"
fi
includes=$(find "$sdk/src/common" "$sdk/src/rp2_common" "$sdk/src/rp2350" -type d -name include \
    | grep -v riscv | sed 's/^/-I/' | tr '\n' ' ')
status=0
for file in "$@"; do
    # shellcheck disable=SC2086
    if ! clang --target=thumbv8m.main-none-eabihf -mcpu=cortex-m33 -ffreestanding -fsyntax-only \
        -std=gnu11 -Wall -Wextra -Wno-unused-parameter -Wno-varargs \
        -DPICO_NO_HARDWARE=0 -DPICO_ON_DEVICE=1 -DPICO_BUILD=1 -DPICO_RP2350=1 -DPICO_32BIT=1 \
        -DLIB_PICO_STDLIB=1 -DPICOCALC \
        -I"$stubs/libc" -I"$stubs/stub" -I"$stubs/gen" $includes -I"$sdk/src/boards/include" \
        -I"$mp/font" -I"$mp/gfx" -I"$mp/PicoCalc/picoware_lcd" "$file"; then
        status=1
    fi
done
[ "$status" -eq 0 ] && echo "Device syntax check passed: $#"
exit "$status"
