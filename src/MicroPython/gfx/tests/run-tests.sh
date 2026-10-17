#!/bin/sh
# Build and run the gfx host tests against the v1 reference driver.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
ref="$here/tests/reference"
font="$here/../font"
out=${TMPDIR:-/tmp}/gfx-tests
cc -std=c99 -O2 -Wall -Wextra -Werror -Wshadow -Wdouble-promotion \
    -I"$font" -o "$out" "$here/gfx.c" "$here/tests/test_gfx.c" \
    "$font"/font8.c "$font"/font12.c "$font"/font16.c "$font"/font20.c "$font"/font24.c \
    -x c -w -I"$ref" -I"$ref/PicoCalc/picoware_lcd" -I"$font" \
    "$ref/PicoCalc/picoware_lcd/picoware_lcd_v1.c" "$ref/stubs.c"
"$out"
