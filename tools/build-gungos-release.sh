#!/bin/sh
# Offline PicoCalc Pico 2 W build from a standalone GungOS release tree.
set -eu
release_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
micropython_root=${MICROPYTHON_DIR:-"$release_root/vendor/micropython"}
build_root=${GUNGOS_BUILD_DIR:-"$release_root/.build"}
jobs=${PICOWARE_BUILD_JOBS:-8}
if [ "${GUNGOS_SKIP_PACKAGE:-0}" != "1" ]; then
    python3 "$release_root/tools/check-build-inputs.py"
fi
for executable in python3 cmake make arm-none-eabi-gcc; do
    command -v "$executable" >/dev/null || { echo "Missing build tool: $executable" >&2; exit 1; }
done
test -f "$micropython_root/ports/rp2/CMakeLists.txt"
test -f "$release_root/vendor/picotool/CMakeLists.txt"
mkdir -p "$build_root" "$release_root/firmware" "$release_root/verification"
export PICOWARE_SOURCE_DIR="$release_root"
gungos_version=$(python3 -c 'import os,runpy; print(runpy.run_path(os.environ["PICOWARE_SOURCE_DIR"]+"/src/MicroPython/picoware/system/features.py")["FIRMWARE_VERSION"])')
# GUNGOS_BUILD_LABEL names a test build in its build string (os.uname().version).
export MICROPY_GIT_TAG="v1.30.0-preview-gungos-v${gungos_version}${GUNGOS_BUILD_LABEL:+-$GUNGOS_BUILD_LABEL}"
export MICROPY_GIT_HASH="424cb8d7a61bf4f7e37bd64bf3d7edc1897cc8b3"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1793664000}"
export MICROPY_MPYCROSS="$build_root/mpy-cross/mpy-cross"
make -C "$micropython_root/mpy-cross" -j"$jobs" BUILD="$build_root/mpy-cross"
# Build the host UF2 conversion tool from the bundled sources, avoiding SDK fetches.
cmake -S "$release_root/vendor/picotool" -B "$build_root/picotool" \
    -DPICO_SDK_PATH="$micropython_root/lib/pico-sdk" \
    -DPICOTOOL_NO_LIBUSB=1 -DPICOTOOL_FLAT_INSTALL=1 \
    -DCMAKE_INSTALL_PREFIX="$build_root/host-tools" \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON
cmake --build "$build_root/picotool" --parallel "$jobs"
cmake --install "$build_root/picotool"
cmake -S "$micropython_root/ports/rp2" -B "$build_root/rp2" \
    -DMICROPY_BOARD=RPI_PICO2_W \
    -DGUNGOS_FAST_PY="${GUNGOS_FAST_PY:-OFF}" \
    -DGUNGOS_FLASH_MAX_HZ="${GUNGOS_FLASH_MAX_HZ:-120000000}" \
    -DMICROPY_BOARD_DIR="$micropython_root/ports/rp2/boards/RPI_PICO2_W" \
    -DUSER_C_MODULES="$release_root/src/MicroPython/PicoCalc/picoware_modules.cmake" \
    -DMICROPY_FROZEN_MANIFEST="$release_root/tools/micropython-picocalc-pico2-w-manifest.py" \
    -DMICROPY_HW_FLASH_STORAGE_BYTES=2048000 \
    -Dpicotool_DIR="$build_root/host-tools/picotool" \
    -DPICO_BUILD_DOCS=0 -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$build_root/rp2" --parallel "$jobs"
if [ "${GUNGOS_SKIP_PACKAGE:-0}" = "1" ]; then
    echo "Native build complete; packaging deferred by GUNGOS_SKIP_PACKAGE."
    exit 0
fi
python3 "$release_root/tools/compile-engineering-apps.py" --mpy-cross "$MICROPY_MPYCROSS" \
    --snapshot "$build_root/sd-app-staging"
python3 "$release_root/tools/finalize-gungos-release.py" --build-dir "$build_root/rp2"
