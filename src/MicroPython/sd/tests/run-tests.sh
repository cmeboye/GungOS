#!/bin/sh
# Build and run the FAT32 driver host tests on an in-memory SD card.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
out=${TMPDIR:-/tmp}/fat32-tests
# The driver keeps its upstream warnings; the test itself builds strictly.
cc -std=gnu11 -O1 -g -w -I"$here/tests/stubs" -I"$here" -c "$here/fat32.c" -o "$out-driver.o"
cc -std=gnu11 -O1 -g -Wall -Wextra -Werror -Wshadow -I"$here/tests/stubs" -I"$here" \
    -o "$out" "$here/tests/test_fat32.c" "$out-driver.o"
"$out"
