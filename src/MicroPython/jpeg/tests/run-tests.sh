#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=$(mktemp -d /tmp/gungos-jpeg-tests.XXXXXX)
trap 'rm -rf "$out"' EXIT HUP INT TERM
c++ -std=c++11 -O2 -Wall -Wextra -Wno-unused-parameter \
    "$here/tests/test_jpeg_output.cpp" "$here/../JPEGDEC/src/JPEGDEC.cpp" \
    -o "$out/test-jpeg"
"$out/test-jpeg" "$@"
