#!/bin/sh

# GB.pak - 320x272 segmented integer scaling on M17
#   8 source rows x1 + 128 source rows x2 + 8 source rows x1 = 272
# The patched gambatte core in this pak reports aspect 320/273, so stock
# minarch's Aspect mode computes a 320-wide destination.
# If minarch.elf is present here it draws that destination in three integer
# scaled segments; otherwise the system minarch.elf is used (plain 1.8889x
# nearest) and the pak still works, just without segmentation.
# Keep the folder name "GB.pak": EMU_TAG drives BIOS/SAVES/LOGS paths.
EMU_EXE=gambatte
CORES_PATH=$(dirname "$0")

###############################

EMU_TAG=$(basename "$(dirname "$0")" .pak)
ROM="$1"
mkdir -p "$BIOS_PATH/$EMU_TAG"
mkdir -p "$SAVES_PATH/$EMU_TAG"
HOME="$USERDATA_PATH"
cd "$HOME"
if [ -f "$CORES_PATH/minarch.elf" ]; then
    # FAT32 cards do not preserve the executable bit; restore it if needed.
    chmod +x "$CORES_PATH/minarch.elf" 2>/dev/null
    MINARCH="$CORES_PATH/minarch.elf"
else
    MINARCH=minarch.elf
fi
"$MINARCH" "$CORES_PATH/${EMU_EXE}_libretro.so" "$ROM" &> "$LOGS_PATH/$EMU_TAG.txt"
