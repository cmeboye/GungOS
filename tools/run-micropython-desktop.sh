#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
picoware_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
build_dir=${PICOWARE_DESKTOP_BUILD_DIR:-"$picoware_dir/builds/MicroPython/desktop"}
binary="$build_dir/micropython"

if [ ! -x "$binary" ] || ! "$binary" -X heapsize=16M -c 'import picoware_desktop; from ulab import numpy as np; assert picoware_desktop.native_modules() == ("auto_complete", "font", "lcd", "picoware_pcm", "response", "ulab", "vector", "vt"); assert np.zeros(1).itemsize == 4; assert hasattr(np, "sort"); assert not hasattr(np.linalg, "inv")' >/dev/null 2>&1; then
    sh "$script_dir/micropython-desktop.sh"
fi

if [ "$#" -eq 0 ]; then
    set -- --viewer --board picocalc-pico2w
else
    has_board=0
    for argument in "$@"; do
        if [ "$argument" = "--board" ]; then
            has_board=1
            break
        fi
    done
    if [ "$has_board" -eq 0 ]; then
        set -- "$@" --board picocalc-pico2w
    fi
fi

cd "$picoware_dir"
# Python mesh objects need more host memory than the firmware's packed triangles.
exec "$binary" -X "heapsize=${PICOWARE_DESKTOP_HEAP_SIZE:-16M}" simulator/run.py "$@"
