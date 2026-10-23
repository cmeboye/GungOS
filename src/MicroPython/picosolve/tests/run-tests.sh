#!/bin/sh
# Build and run the picosolve host tests with strict warnings.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
out=${TMPDIR:-/tmp}/picosolve-tests
flags="-std=c99 -O2 -Wall -Wextra -Werror -Wshadow -Wdouble-promotion -pedantic"
# shellcheck disable=SC2086
cc $flags -o "$out" "$here"/core/*.c "$here"/fe/*.c "$here"/tests/test_picosolve.c -lm
"$out"
# shellcheck disable=SC2086
cc $flags -o "$out-circuit" "$here"/core/sparse.c "$here"/fe/circuit.c "$here"/tests/test_circuit.c -lm
"$out-circuit"
# shellcheck disable=SC2086
cc $flags -o "$out-formula" "$here"/expr/formula.c "$here"/tests/test_formula.c -lm
"$out-formula"
