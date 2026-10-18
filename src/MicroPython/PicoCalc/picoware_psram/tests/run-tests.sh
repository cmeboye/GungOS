#!/bin/sh
# Exercise the actual device PSRAM binding; emulate only the QSPI chip/bus.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH= cd -- "$here/../../../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/gungos-psram-test.XXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
mkdir -p "$work/modules/psram"
cp "$here/../picoware_psram.c" "$here/../picoware_psram.h" "$here/../picoware_psram_shared.h" "$here/psram_qspi.h" "$here/fake_qspi.c" "$work/modules/psram/"
cat > "$work/modules/psram/micropython.mk" <<'MAKE'
SRC_USERMOD += $(USERMOD_DIR)/picoware_psram.c
SRC_USERMOD += $(USERMOD_DIR)/fake_qspi.c
MAKE
make -C "$root/vendor/micropython/ports/unix" -j"${PICOWARE_BUILD_JOBS:-8}" \
    BUILD="$work/build" VARIANT_DIR="$root/src/MicroPython/Desktop/variant" \
    USER_C_MODULES="$work/modules" FROZEN_MANIFEST= MICROPY_PY_FFI=0 \
    CFLAGS_EXTRA=-Wno-error
cd "$root"
"$work/build/micropython" -X heapsize=16M "$here/test_lifetime.py"
