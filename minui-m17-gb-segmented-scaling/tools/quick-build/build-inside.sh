#!/bin/sh
# Build minarch.elf inside the m17-quick container.
# Host invocation (Git Bash):
#   MSYS2_ARG_CONV_EXCL='*' docker run --rm \
#     -v "/path/to/MinUI/workspace:/root/workspace" \
#     m17-quick sh /root/workspace/../build-inside.sh
# Simpler: mount the workspace and copy this script into /root first.
set -e

WS=/root/workspace
export CROSS_COMPILE=arm-linux-gnueabihf-
export PREFIX=/usr/arm-linux-gnueabihf
export UNION_PLATFORM=m17

echo "== compiler =="
"${CROSS_COMPILE}gcc" --version | head -1

echo "== libmsettings =="
cd "$WS/m17/libmsettings"
"${CROSS_COMPILE}gcc" -shared -fPIC -O2 -o "$PREFIX/lib/libmsettings.so" msettings.c -ldl -lrt
cp msettings.h "$PREFIX/include/"

echo "== minarch =="
cd "$WS/all/minarch"
# Debian's armhf cross compiler defaults to vfpv3-d16; the LTO stage emits
# NEON q8-q15 register lists, so the m17 build needs -mfpu=neon explicitly.
# Debian gcc also defaults to PIE while the stock minarch.elf is EXEC;
# force -no-pie so the output matches the official binary type exactly.
make PLATFORM=m17 \
  ARCH="-O3 -mfpu=neon -fno-pie" \
  LIBS="-flto -mfpu=neon -no-pie"

cp build/m17/minarch.elf "$WS/minarch-segmented.elf"
echo "OK: $WS/minarch-segmented.elf ($(wc -c < "$WS/minarch-segmented.elf") bytes)"
