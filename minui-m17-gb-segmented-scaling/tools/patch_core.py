#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Make a GB.pak-only 320x272 scaling variant WITHOUT compiling anything.

MinUI's M17 minarch draws the Aspect mode with (PLAT_flip in
workspace/m17/platform/platform.c):

    int h = FIXED_HEIGHT;              // 273
    int w = h * vid.blit->aspect;      // aspect == core.aspect_ratio
    int x = (FIXED_WIDTH - w) / 2;    // 480

core.aspect_ratio comes from retro_get_system_av_info()'s
geometry.aspect_ratio (a float) reported by the libretro core. In the M17
gambatte_libretro.so shipped with MinUI v20251127-1, that float is materialized
by two immediate instructions inside retro_get_system_av_info():

    0x4a51c: movw r1, #0x38e4
    0x4a53c: movt r1, #0x3f8e   -> r1 = 0x3f8e38e4 = float(10/9)
    0x4a560: str  r1, [r0,#0x10] -> geometry.aspect_ratio

Replacing those two immediates with a float slightly above 320/273 makes the
*unmodified* minarch draw w == 320, x == 80, h == 273 (272 visible rows on the
480x272 framebuffer). Menu_scale() and selectScaler() also derive their
geometry from core.aspect_ratio, so previews stay in sync automatically.

Only 8 bytes change. No ARM toolchain, no Docker, no source rebuild.

Usage:
    python patch_core.py --input gambatte_libretro.so --output GB.pak/gambatte_libretro.so

Input must be the M17 core from:
    MinUI-20251127-1-base.zip / MinUI.zip /
    .system/m17/cores/gambatte_libretro.so   (1139472 bytes)
"""
import argparse
import hashlib
import struct
from pathlib import Path

MOVW_OFF = 0x4A51C
MOVT_OFF = 0x4A53C
EXPECT_MOVW = 0xE30318E4  # movw r1, #0x38e4
EXPECT_MOVT = 0xE3431F8E  # movt r1, #0x3f8e
EXPECT_SIZE = 1139472

FIXED_WIDTH = 480
FIXED_HEIGHT = 273
TARGET_W = 320


def encode_mov(imm16, top):
    """ARM (A32, LE) movw/movt r1, #imm16."""
    opcode = 0xE3400000 if top else 0xE3000000
    return opcode | 0x1000 | (((imm16 >> 12) & 0xF) << 16) | (imm16 & 0xFFF)


def choose_aspect():
    """Smallest margin that survives float32 -> double -> int truncation."""
    for margin in (0.0, 0.0001, 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0):
        a = (TARGET_W + margin) / FIXED_HEIGHT
        bits = struct.unpack("<I", struct.pack("<f", a))[0]
        f = struct.unpack("<f", struct.pack("<I", bits))[0]
        if TARGET_W <= FIXED_HEIGHT * f < TARGET_W + 1:
            return a, f, bits, margin
    raise RuntimeError("no suitable aspect ratio found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="original M17 gambatte_libretro.so")
    ap.add_argument("--output", required=True, help="patched .so path")
    args = ap.parse_args()

    src = Path(args.input)
    dst = Path(args.output)
    orig = src.read_bytes()
    if len(orig) != EXPECT_SIZE:
        raise SystemExit("unexpected core size %d (want %d); wrong platform/version?"
                         % (len(orig), EXPECT_SIZE))
    if orig[4:6] != b"\x01\x01" or struct.unpack_from("<H", orig, 18)[0] != 40:
        raise SystemExit("not a little-endian ELF32 ARM binary")

    w0 = struct.unpack_from("<I", orig, MOVW_OFF)[0]
    w1 = struct.unpack_from("<I", orig, MOVT_OFF)[0]
    if (w0, w1) != (EXPECT_MOVW, EXPECT_MOVT):
        raise SystemExit("instruction pattern mismatch: %08x %08x (want %08x %08x)"
                         % (w0, w1, EXPECT_MOVW, EXPECT_MOVT))
    old_bits = (((EXPECT_MOVT >> 16) & 0xF) << 12 | (EXPECT_MOVT & 0xFFF)) << 16 \
               | (((EXPECT_MOVW >> 16) & 0xF) << 12 | (EXPECT_MOVW & 0xFFF))
    old_float = struct.unpack("<f", struct.pack("<I", old_bits))[0]

    a, f, bits, margin = choose_aspect()
    low, high = bits & 0xFFFF, bits >> 16
    new_w0 = encode_mov(low, False)
    new_w1 = encode_mov(high, True)

    buf = bytearray(orig)
    struct.pack_into("<I", buf, MOVW_OFF, new_w0)
    struct.pack_into("<I", buf, MOVT_OFF, new_w1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf)

    # ---- self-check ----
    out = dst.read_bytes()
    diffs = [i for i in range(len(orig)) if orig[i] != out[i]]
    assert len(out) == len(orig)
    allowed = set(range(MOVW_OFF, MOVW_OFF + 4)) | set(range(MOVT_OFF, MOVT_OFF + 4))
    assert 0 < len(diffs) <= 8 and set(diffs) <= allowed
    assert struct.unpack_from("<I", out, MOVW_OFF)[0] == new_w0
    assert struct.unpack_from("<I", out, MOVT_OFF)[0] == new_w1
    w = int(FIXED_HEIGHT * f)
    x = (FIXED_WIDTH - w) // 2
    assert w == 320 and x == 80 and FIXED_WIDTH - w - x == 80
    assert w <= FIXED_WIDTH  # no letterbox branch

    print("original float   : %.9f (0x%08x) = 10/9" % (old_float, old_bits))
    print("patched  float   : %.9f (0x%08x)  margin=%.4g" % (f, bits, margin))
    print("instructions     : %08x -> %08x , %08x -> %08x"
          % (EXPECT_MOVW, new_w0, EXPECT_MOVT, new_w1))
    print("changed bytes    : %d (offsets %s)" % (len(diffs), [hex(i) for i in diffs]))
    print("PLAT_flip Aspect : h=%d w=%d x=%d y=0 -> left/right bars 80/80"
          % (FIXED_HEIGHT, w, x))
    print("GB 160x144       : x-scale %.4f, y-scale %.4f (272 visible rows)"
          % (w / 160, 272 / 144))
    print("sha256 orig      : %s" % hashlib.sha256(orig).hexdigest())
    print("sha256 patched   : %s" % hashlib.sha256(out).hexdigest())
    print("output           : %s (%d bytes)" % (dst, len(out)))

    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
        for off in (MOVW_OFF, MOVT_OFF):
            ins = next(md.disasm(out[off:off + 4], off))
            print("disasm 0x%x      : %s %s" % (off, ins.mnemonic, ins.op_str))
    except ImportError:
        print("disasm           : skipped (capstone not installed)")


if __name__ == "__main__":
    main()
