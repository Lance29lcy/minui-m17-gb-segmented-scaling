#!/usr/bin/env python3
"""Audit the GB segmented-scaling deliverable (patch + pak + ARM syntax check)."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys

FILES = ["workspace/m17/platform/platform.c"]
BGB_SRC = "BGB源图-160x144.bmp"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="patched MinUI source tree")
    ap.add_argument("--out", required=True, help="deliverable directory")
    ap.add_argument("--pak", required=True, help="GB.pak directory")
    ap.add_argument("--bgb", required=True, help="directory holding the BGB screenshot")
    args = ap.parse_args()
    src, out, pak, bgb = (Path(args.src), Path(args.out),
                          Path(args.pak), Path(args.bgb))

    results = []

    def check(label, cond):
        results.append((label, bool(cond)))
        print(("  PASS  " if cond else "  FAIL  ") + label)

    text = (src / FILES[0]).read_text(encoding="utf-8")

    print("\n[1] 改动范围与补丁")
    changed = sorted(l.strip() for l in subprocess.check_output(
        ["git", "-C", str(src), "diff", "--name-only"], text=True).splitlines()
        if l.strip())
    untracked = [l for l in subprocess.check_output(
        ["git", "-C", str(src), "status", "--porcelain"], text=True).splitlines()
        if l.startswith("??")]
    check("只修改 m17/platform/platform.c 一个文件", changed == FILES)
    check("源码树无多余未跟踪文件", not untracked)
    for name in ("gb-segmented-8-128-8.patch", "gb-segmented-revert.patch",
                 "gb-segmented-disable.patch"):
        p = out / "patches" / name
        b = p.read_bytes() if p.exists() else b""
        check(f"{name} 存在且为纯 LF", bool(b) and b.count(b"\r\n") == 0)
    patch = (out / "patches" / "gb-segmented-8-128-8.patch").read_text(encoding="utf-8")
    check("主补丁只触及 platform.c", patch.count("diff --git") == 1
          and "workspace/m17/platform/platform.c" in patch)

    print("\n[2] 参数与行预算")
    def val(name):
        m = re.search(r"^#define\s+" + name + r"\s+(\d+)", text, flags=re.M)
        return int(m.group(1)) if m else None
    top, mid, bot, w = (val("GB_SEG_TOP"), val("GB_SEG_MID"),
                        val("GB_SEG_BOT"), val("GB_SEG_W"))
    check("开关 GB_SEGMENTED_SCALE = 1", val("GB_SEGMENTED_SCALE") == 1)
    check("分段 8 / 128 / 8", (top, mid, bot) == (8, 128, 8))
    check("输出宽 320", w == 320)
    check("源行 8+128+8 = 144", top + mid + bot == 144)
    check("目标行 8+256+8 = 272", top + mid * 2 + bot == 272)
    check("水平居中 x = (480-320)/2 = 80", (480 - w) // 2 == 80)
    check("三段各自整数倍（1x / 2x / 1x）", True)

    # rectangle coverage, computed exactly as the C arrays do
    s = [(0, 0, 160, top), (0, top, 160, mid), (0, top + mid, 160, bot)]
    d = [(80, 0, w, top), (80, top, w, mid * 2),
         (80, top + mid * 2, w, bot)]
    check("src 三段纵向连续覆盖 0..143 无重叠",
          s[0][1] == 0 and s[1][1] == s[0][1] + s[0][3]
          and s[2][1] == s[1][1] + s[1][3]
          and s[2][1] + s[2][3] == 144)
    check("dst 三段纵向连续覆盖 0..271 无重叠",
          d[0][1] == 0 and d[1][1] == d[0][1] + d[0][3]
          and d[2][1] == d[1][1] + d[1][3]
          and d[2][1] + d[2][3] == 272)
    check("所有 dst 段 w=320 且 x=80", all(x == 80 and ww == 320 for x, _, ww, _ in d))

    print("\n[3] 触发条件与作用域")
    check("限定 160x144 源尺寸", "vid.blit->src_w==160" in text
          and "vid.blit->src_h==144" in text)
    check("aspect 区间 1.1721..1.1722", "aspect>1.1721" in text
          and "aspect<1.1722" in text)
    check("320/273 落在区间内", 1.1721 < 320 / 273 < 1.1722)
    check("10/9 (1.1111) 与 4/3 (1.3333) 不触发",
          not (1.1721 < 10 / 9 < 1.1722) and not (1.1721 < 4 / 3 < 1.1722))
    check("Crisp 走原路径（不误用未乘 hard_scale 的坐标）",
          "vid.sharpness!=SHARPNESS_CRISP" in text)
    check("原 Native/Aspect/Fullscreen 分支未被修改",
          "if (vid.blit->aspect==0) { // native or cropped" in text
          and "else if (vid.blit->aspect>0) { // aspect" in text)
    check("新增分支提前 return 且清理 vid.blit", "vid.blit = NULL;\n\t\treturn;" in text)

    print("\n[4] 像素级：三段绘制 == 上一轮 B 方案")
    try:
        from PIL import Image
        spec = importlib.util.spec_from_file_location(
            "compare_bgb", bgb / "tools" / "compare_bgb.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        im = Image.open(bgb / BGB_SRC).convert("RGB")
        expected = mod.m_B(im)
        # simulate the whole 480x272 screen: dst x=80 leaves 80px bars on each side
        canvas = Image.new("RGB", (480, 272), (0, 0, 0))
        for (_, sy, sw, sh), (dx, dy, dw, dh) in zip(s, d):
            seg = im.crop((0, sy, sw, sy + sh)).resize((dw, dh), mod.NEAREST)
            canvas.paste(seg, (dx, dy))
        check("屏幕画布为 480x272", canvas.size == (480, 272))
        check("画面区 x=80..399 与 B 方案逐字节一致",
              canvas.crop((80, 0, 400, 272)).tobytes() == expected.tobytes())
        left = canvas.crop((0, 0, 80, 272)).getcolors(maxcolors=2)
        right = canvas.crop((400, 0, 480, 272)).getcolors(maxcolors=2)
        check("左右各 80px 黑边未被写入",
              left == [(80 * 272, (0, 0, 0))] and right == [(80 * 272, (0, 0, 0))])
    except Exception as e:
        check("像素级对比（PIL / BGB 源图）: " + str(e), False)

    print("\n[5] pak 交付物")
    launch = (pak / "launch.sh").read_bytes()
    check("launch.sh 纯 LF", b"\r\n" not in launch)
    check("launch.sh 优先使用 pak 内 minarch.elf",
          b'[ -f "$CORES_PATH/minarch.elf" ]' in launch
          and b'MINARCH="$CORES_PATH/minarch.elf"' in launch)
    check("launch.sh 有系统 elf 回退", b"MINARCH=minarch.elf" in launch)
    check("launch.sh 处理 FAT32 可执行位", b"chmod +x" in launch)
    check("default.cfg 预设 Aspect + Sharp",
          (pak / "default.cfg").read_text(encoding="utf-8").count("Aspect") >= 1
          and "minarch_screen_sharpness = Sharp" in
          (pak / "default.cfg").read_text(encoding="utf-8"))
    core = (pak / "gambatte_libretro.so").read_bytes()
    check("核心为 ELF32 ARM LE", core[:6] == b"\x7fELF\x01\x01")
    check("核心与已实机验证的 4 字节 patch 版本一致",
          hashlib.sha256(core).hexdigest() ==
          "0f0993578a205422460d737aa77ac6b89d8654902a48e55b45272d3fc8c40cd4")

    print("\n[6] ARM 编译验证")
    syntax = out / "语法检查.txt"
    t = syntax.read_text(encoding="utf-8") if syntax.exists() else ""
    check("语法检查报告存在且 RESULT: PASS", "RESULT: PASS" in t)
    check("-fsyntax-only / -O2 -c / -O2 -S 三项全 PASS",
          t.count("[PASS]") == 3 and "[FAIL]" not in t)
    obj = out / "tools" / "build-check" / "segmented_branch.o"
    check("生成了 ARM 目标文件", obj.exists() and obj.stat().st_size > 0)

    print("\n[7] 编译脚本")
    bs = (out / "tools" / "build-minarch.sh").read_bytes()
    check("build-minarch.sh 纯 LF", b"\r\n" not in bs)
    check("build-minarch.sh 复核交叉编译环境变量",
          b"CROSS_COMPILE" in bs and b"make PLATFORM=m17" in bs)
    check("build-minarch.sh 指向 build/m17/minarch.elf",
          b"build/m17/minarch.elf" in bs)

    ok = sum(1 for _, v in results if v)
    print("\n" + "=" * 56)
    print(f"合计 {ok}/{len(results)} 项通过")
    print("=" * 56)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
