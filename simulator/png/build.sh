#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
cc -std=c11 -O2 -DZ_PREFIX -Isrc/MicroPython/png/upstream \
    ${PNG_TEST_CFLAGS:-} simulator/png/decode.c src/MicroPython/png/png_core.c \
    src/MicroPython/png/upstream/adler32.c src/MicroPython/png/upstream/crc32.c \
    src/MicroPython/png/upstream/inffast.c src/MicroPython/png/upstream/inflate.c \
    src/MicroPython/png/upstream/inftrees.c src/MicroPython/png/upstream/zutil.c \
    -o "${PNG_TEST_BINARY:-/tmp/gungos-png-decode}"
