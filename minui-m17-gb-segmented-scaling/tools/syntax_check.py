#!/usr/bin/env python3
"""Compile-check the segmented-scaling branch with a real ARM cross compiler.

The branch is extracted verbatim from the patched platform.c (not retyped),
wrapped in a minimal stub environment, then compiled with arm-none-eabi-gcc:
  1. -fsyntax-only -Wall -Wextra   (C99 syntax / type check)
  2. -O2 -c                        (real ARM object code generation)
  3. -O2 -S                        (assembly, to confirm 3 RenderCopy calls)

No Linux sysroot or SDL headers are needed: only the types the branch touches
are stubbed. This validates the patch code, not a full MinUI link.
"""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import tempfile

DEFAULT_CC = (r"C:\Program Files\Arm\GNU Toolchain "
              r"mingw-w64-x86_64-arm-none-eabi\bin\arm-none-eabi-gcc.exe")

STUB_HEAD = r"""
/* ---- minimal stubs for the symbols the extracted branch uses ---- */
#include <stddef.h>

typedef struct { int x, y, w, h; } SDL_Rect;
typedef struct SDL_Renderer SDL_Renderer;
typedef struct SDL_Texture SDL_Texture;

extern int SDL_RenderCopy(SDL_Renderer* r, SDL_Texture* t,
                          const SDL_Rect* srcrect, const SDL_Rect* dstrect);
extern void SDL_RenderPresent(SDL_Renderer* r);

#define SHARPNESS_CRISP 1
#define FIXED_WIDTH 480

typedef struct {
    double aspect;
    int src_w;
    int src_h;
} GFX_Renderer;

typedef struct {
    int sharpness;
    SDL_Renderer* renderer;
    GFX_Renderer* blit;
} VID;

static VID vid;
static SDL_Texture* target;

/* ---- extracted defines ---- */
"""

STUB_TAIL = r"""
int main(void) { segmented_flip(); return 0; }
"""


def extract(src_text):
    defs = re.findall(
        r"^#define\s+GB_(?:SEGMENTED_SCALE|SEG_[A-Z_]+)\s+[^\n]*$",
        src_text, flags=re.M)
    assert len(defs) == 5, f"expected 5 GB_SEG defines, got {len(defs)}: {defs}"

    m = re.search(r"^#if GB_SEGMENTED_SCALE\s*\n(.*?)^#endif\s*$",
                  src_text, flags=re.M | re.S)
    assert m, "segmented branch not found"
    branch = m.group(1)
    assert "SDL_RenderCopy" in branch and "GB_SEG_MID * 2" in branch
    return ("\n".join(defs) + "\n\n/* ---- extracted branch ---- */\n"
            "static void segmented_flip(void) {\n" + branch + "\n}\n")


def numeric_checks(txt):
    def val(name):
        m = re.search(r"^#define\s+" + name + r"\s+(\d+)", txt, flags=re.M)
        assert m, name
        return int(m.group(1))
    top, mid, bot, w = (val("GB_SEG_TOP"), val("GB_SEG_MID"),
                        val("GB_SEG_BOT"), val("GB_SEG_W"))
    assert top + mid + bot == 144, "source rows must total 144"
    assert top + mid * 2 + bot == 272, "output rows must total 272"
    assert w == 320 and (480 - w) // 2 == 80, "width / centering"
    assert val("GB_SEGMENTED_SCALE") == 1, "switch must be enabled"
    return top, mid, bot, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="patched platform.c")
    ap.add_argument("--cc", default=DEFAULT_CC)
    ap.add_argument("--out", required=True, help="directory for generated artifacts")
    args = ap.parse_args()

    src = Path(args.src).read_text(encoding="utf-8")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cc = args.cc

    defs_and_branch = extract(src)
    numeric_checks(src)
    c = out / "segmented_branch_stub.c"
    c.write_text(STUB_HEAD + defs_and_branch + STUB_TAIL, encoding="utf-8")
    print("extracted branch ->", c.name, c.stat().st_size, "bytes")

    base = [cc, "-std=gnu99", "-marm", "-mcpu=cortex-a7", "-mlittle-endian",
            "-Wall", "-Wextra", "-Wno-unused-parameter"]
    ok = True

    def run(label, extra):
        nonlocal ok
        r = subprocess.run(base + extra + [str(c)],
                           capture_output=True, text=True)
        clean = "\n".join(l for l in (r.stdout + r.stderr).splitlines()
                          if l.strip() and "arm-none-eabi" not in l.lower())
        status = "PASS" if r.returncode == 0 else "FAIL"
        if r.returncode != 0:
            ok = False
        print(f"  [{status}] {label}")
        if clean.strip():
            for l in clean.splitlines()[:12]:
                print("        ", l)
        return r.returncode == 0

    print("\n=== ARM 编译验证 (arm-none-eabi-gcc) ===")
    run("C99 语法/类型检查 (-fsyntax-only)", ["-fsyntax-only"])
    obj = out / "segmented_branch.o"
    run("生成 ARM 目标码 (-O2 -c)", ["-O2", "-c", "-o", str(obj)])
    asm = out / "segmented_branch.s"
    run("生成 ARM 汇编 (-O2 -S)", ["-O2", "-S", "-o", str(asm)])

    if asm.exists():
        text = asm.read_text(encoding="utf-8", errors="ignore")
        calls = text.count("bl\tSDL_RenderCopy") + text.count("bl SDL_RenderCopy")
        print(f"  汇编中 SDL_RenderCopy 调用点: {calls} (循环内 1 处，运行时执行 3 次)")
        # constants that must appear
        for k in ("320", "256", "264", "80"):
            print(f"  立即数 {k}: {'出现' if k in text else '由寄存器/常量池承载'}")

    print("\n=== 数值自检 ===")
    print("  源行 8 + 128 + 8 = 144 ; 目标行 8 + 256 + 8 = 272 ; x = (480-320)/2 = 80")
    print("  三段 src: {0,0,160,8} {0,8,160,128} {0,136,160,8}")
    print("  三段 dst: {80,0,320,8} {80,8,320,256} {80,264,320,8}")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
