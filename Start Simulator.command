#!/bin/sh
set -eu
gungos_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$gungos_root/.build"
export MICROPYTHON_DIR="$gungos_root/vendor/micropython"
export PICOWARE_DESKTOP_SOURCE_ALIAS="$gungos_root/.build/desktop-source"
exec sh "$gungos_root/tools/run-micropython-desktop.sh" --viewer --board picocalc-pico2w "$@"
