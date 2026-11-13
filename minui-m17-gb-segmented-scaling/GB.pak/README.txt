GB.pak — MinUI (M17) GB 8/128/8 segmented scaling
===================================================

WHAT'S IN HERE
  launch.sh                  MinUI pak launcher. Prefers the bundled minarch.elf;
                             falls back to the system .system/m17/bin/minarch.elf.
  default.cfg                Presets: Screen Scaling = Aspect, Sharpness = Sharp.
  minarch.elf                Compiled with the segmented PLAT_flip() patch.
                             72,816 bytes, ELF32/ARM/hard-float/EXEC.
  README.txt / 使用须知.txt   This file and the Chinese quick guide.

WHAT'S DELIBERATELY MISSING
  gambatte_libretro.so       Upstream official core is NOT redistributed here
                             (no LICENSE in the upstream repo). Get it from
                             MinUI release v20251127-1, then run:

    python ../tools/patch_core.py \
        --input /path/to/gambatte_libretro.so \
        --output gambatte_libretro.so

  This byte patch is REQUIRED: the segmented branch triggers only when the
  core reports aspect_ratio = 320/273. A stock core reports 10/9 and will
  silently take the original scaling path.

INSTALL
  Copy the whole GB.pak/ folder to /sdcard/Emus/m17/GB.pak/ (keep the name).
  In-game: Menu -> Options -> Screen Scaling = Aspect, Sharpness = Sharp.
  Do NOT use Crisp (it pre-scales x4; the code deliberately skips it).
  A user cfg under .userdata overrides default.cfg -- reselect in the menu
  if you changed scaling before.

ROLLBACK
  Delete GB.pak/minarch.elf          -> stock Aspect + nearest 1.8889x
  Delete /sdcard/Emus/m17/GB.pak/   -> completely back to stock MinUI
  Nothing under .system/ is ever modified.

See ../README.md and ../LICENSE-NOTICE.md for details and provenance.
