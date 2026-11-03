# PNGdec inflate engine

Source: https://github.com/bitbank2/PNGdec
Revision: 2855e785bc1a80763c89a2afd808faf6156d35c6 (1.1.7)

These files are the PNGdec fork of zlib. Its inflater accepts a
caller-owned state and 32 KiB window, avoiding hidden malloc calls. Preserve
the zlib notices in each source and the upstream repository license.

GungOS uses its own bounded PNG chunk parser, filters and RGB332 compositor
in ../png_core.c. The upstream image parser/converter is not compiled: its
chunk buffering and packed-pixel/transparency paths did not meet our checks.
Local change: inflate.c disables ALLOWS_UNALIGNED. Its repeat-pattern word
copy can overshoot avail_out by three bytes and triggers undefined unaligned
accesses. The original bounded byte-copy fallback is used on host and device.

Z_PREFIX isolates the fork from any other zlib in firmware. Do not call
inflateEnd: the fork's state/window belong to our single workspace.
