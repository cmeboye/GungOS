#!/bin/sh
# Build and run the picosolve host tests with strict warnings.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
out=${TMPDIR:-/tmp}/picosolve-tests
cc -std=c99 -O2 -Wall -Wextra -Werror -Wshadow -Wdouble-promotion -pedantic \
    -o "$out" "$here"/core/*.c "$here"/fe/*.c "$here"/tests/test_picosolve.c -lm
"$out"
