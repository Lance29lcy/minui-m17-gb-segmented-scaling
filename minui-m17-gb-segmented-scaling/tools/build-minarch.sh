#!/bin/sh
# Build minarch.elf with the segmented PLAT_flip() patch.
#
# Run this INSIDE the MinUI build container, on the HOST first do:
#   cd /path/to/MinUI
#   git apply /path/to/gb-segmented-8-128-8.patch
#   make shell PLATFORM=m17
# then inside the container:
#   sh /root/workspace/tools/build-minarch.sh /root/workspace/minarch-segmented.elf
# finally copy that file into GB.pak/ on the SD card.
#
# The toolchain image is built by makefile.toolchain. If a prebuilt
# m17-toolchain.tar.xz is placed in the toolchain repo's support/ folder,
# build-toolchain.sh unpacks it instead of compiling buildroot for hours.
set -e

WS="${MINUI_WS:-/root/workspace}"
OUT="${1:-$WS/minarch-segmented.elf}"

if [ -z "$CROSS_COMPILE" ] || [ -z "$PREFIX" ]; then
    echo "ERROR: CROSS_COMPILE / PREFIX are not set." >&2
    echo "Run 'make shell PLATFORM=m17' and execute this script in that shell," >&2
    echo "or source the toolchain setup-env.sh first." >&2
    exit 1
fi

echo "CC      = ${CROSS_COMPILE}gcc"
echo "PREFIX  = $PREFIX"
echo "SOURCE  = $WS/all/minarch"

# libmsettings header is a prerequisite of the minarch makefile
if [ ! -f "$PREFIX/include/msettings.h" ]; then
    echo "building libmsettings ..."
    (cd "$WS/m17/libmsettings" && make)
fi

cd "$WS/all/minarch"
make PLATFORM=m17

ELF="build/m17/minarch.elf"
[ -f "$ELF" ] || { echo "ERROR: $ELF not produced" >&2; exit 1; }
cp "$ELF" "$OUT"
chmod +x "$OUT"
echo "OK: $OUT ($(wc -c < "$OUT") bytes)"
echo "Copy it to /sdcard/Emus/m17/GB.pak/minarch.elf"
