#!/usr/bin/env python3
"""Verify the locally compiled minarch.elf against the stock M17 binary.

Checks ABI, dynamic dependencies, glibc symbol versions, undefined symbols and
disassembly evidence for the 8/128/8 segmented RenderCopy path.

Requires arm-none-eabi-readelf / arm-none-eabi-objdump on PATH.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

READELF = shutil.which("arm-none-eabi-readelf")
OBJDUMP = shutil.which("arm-none-eabi-objdump")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout


def header(path):
    return run([READELF, "-h", path])


def program(path):
    return run([READELF, "-l", path])


def dynamic(path):
    return run([READELF, "-d", path])


def versions(path):
    return run([READELF, "--version-info", path])


def symbols(path):
    return run([READELF, "-sW", path])


def attributes(path):
    return run([READELF, "-A", path])


def disasm(path, symbol=None):
    cmd = [OBJDUMP, "-d"]
    if symbol:
        cmd.append("--disassemble=" + symbol)
    cmd.append(path)
    return run(cmd)


def needed(text):
    return sorted(set(re.findall(r"Shared library: \[([^\]]+)\]", text)))


def und_symbols(text):
    names = set()
    for line in text.splitlines():
        if " UND " in line:
            name = line.split()[-1].split("@")[0]
            names.add(name)
    return names


def glibc_versions(text):
    return sorted(set(re.findall(r"GLIBC_(\d+\.\d+)", text)), key=lambda s: tuple(map(int, s.split("."))))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--pak", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if not READELF or not OBJDUMP:
        print("ERROR: arm-none-eabi-readelf / arm-none-eabi-objdump not on PATH")
        return 2

    lines = []
    passed = failed = 0

    def check(label, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
            lines.append("  PASS  " + label + (("  | " + detail) if detail else ""))
        else:
            failed += 1
            lines.append("  FAIL  " + label + (("  | " + detail) if detail else ""))

    elf, ref = a.elf, a.reference
    h_new, h_ref = header(elf), header(ref)
    d_new, d_ref = dynamic(elf), dynamic(ref)
    p_new, p_ref = program(elf), program(ref)
    v_new, v_ref = versions(elf), versions(ref)
    s_new, s_ref = symbols(elf), symbols(ref)
    attr = attributes(elf)
    dis_new, dis_ref = disasm(elf), disasm(ref)

    flip_sym = ""
    for line in s_new.splitlines():
        if "PLAT_flip" in line:
            flip_sym = line.split()[-1]
            break
    dis_flip = disasm(elf, flip_sym) if flip_sym else ""

    lines.append("=" * 60)
    lines.append("minarch.elf 本机构建产物核对")
    lines.append("=" * 60)
    lines.append("目标   : " + os.path.abspath(elf))
    lines.append("对照   : " + os.path.abspath(ref))
    lines.append("目标   : %d bytes  sha256=%s" % (os.path.getsize(elf), sha256(elf)))
    lines.append("对照   : %d bytes  sha256=%s" % (os.path.getsize(ref), sha256(ref)))

    lines.append("")
    lines.append("[1] ELF 基本属性")
    check("ELF32 / little endian / ARM",
          "ELF32" in h_new and "little endian" in h_new and "Machine:                           ARM" in h_new)
    check("hard-float ABI (0x5000400)", "hard-float ABI" in h_new, "官方：" + ("hard-float" if "hard-float ABI" in h_ref else "?"))
    check("Type = EXEC，与官方一致", "Type:                              EXEC" in h_new and "EXEC" in h_ref)
    interp_new = re.search(r"Requesting program interpreter: ([^\]]+)", p_new)
    interp_ref = re.search(r"Requesting program interpreter: ([^\]]+)", p_ref)
    check("PT_INTERP = /lib/ld-linux-armhf.so.3 且一致",
          bool(interp_new and interp_ref and interp_new.group(1) == interp_ref.group(1) == "/lib/ld-linux-armhf.so.3"))

    lines.append("")
    lines.append("[2] 动态依赖与符号版本")
    n_new, n_ref = needed(d_new), needed(d_ref)
    check("DT_NEEDED 集合与官方完全相同（9 项）", n_new == n_ref and len(n_new) == 9, ",".join(n_new))
    gv_new, gv_ref = glibc_versions(v_new), glibc_versions(v_ref)
    check("glibc 版本需求与官方一致", gv_new == gv_ref, "目标=" + ",".join(gv_new) + " 官方=" + ",".join(gv_ref))
    check("无 GLIBC_2.28+ 新符号（设备 glibc 2.26 可加载）",
          all(tuple(map(int, v.split("."))) <= (2, 7) for v in gv_new))
    u_new, u_ref = und_symbols(s_new), und_symbols(s_ref)
    extra = sorted(u_new - u_ref)
    check("未定义符号未新增（设备不会找不到符号）", not extra, "新增=" + (",".join(extra) or "无"))
    check("官方独有多余符号仅 _Jv_RegisterClasses 类无关项",
          sorted(u_ref - u_new) == ["_Jv_RegisterClasses"], "差异=" + ",".join(sorted(u_ref - u_new)))

    lines.append("")
    lines.append("[3] ARM 属性")
    check("CPU = ARMv7-A (Cortex-A7 匹配)", "Tag_CPU_name: \"7-A\"" in attr)
    check("NEONv1 + VFP registers 调用约定", "NEONv1" in attr and "Tag_ABI_VFP_args: VFP registers" in attr)

    lines.append("")
    lines.append("[4] 分段绘制代码证据（反汇编）")
    rc_new = len(re.findall(r"blx?\s+\S+\s+<SDL_RenderCopy@plt>", dis_new))
    rc_ref = len(re.findall(r"blx?\s+\S+\s+<SDL_RenderCopy@plt>", dis_ref))
    rp_new = len(re.findall(r"blx?\s+\S+\s+<SDL_RenderPresent@plt>", dis_new))
    rp_ref = len(re.findall(r"blx?\s+\S+\s+<SDL_RenderPresent@plt>", dis_ref))
    check("SDL_RenderCopy 调用点比官方多 3（三段展开）", rc_new - rc_ref == 3, "官方=%d 目标=%d" % (rc_ref, rc_new))
    check("SDL_RenderPresent 调用点比官方多 1（分段分支提前 return）", rp_new - rp_ref == 1, "官方=%d 目标=%d" % (rp_ref, rp_new))
    check("PLAT_flip 内存在连续三次 RenderCopy + Present",
          bool(flip_sym) and len(re.findall(r"<SDL_RenderCopy@plt>", dis_flip)) >= 4
          and "<SDL_RenderPresent@plt>" in dis_flip,
          "符号=" + (flip_sym or "未找到"))
    consts = set()
    for m in re.finditer(r"#\s*(\d+)", dis_new):
        consts.add(int(m.group(1)))
    for m in re.finditer(r"@ 0x([0-9a-f]+)", dis_new):
        consts.add(int(m.group(1), 16))
    need = {8, 128, 160, 256, 272, 320}
    check("机器码含 8/128/160/256/272/320 全套分段常数", need <= consts,
          "缺失=" + (",".join(map(str, sorted(need - consts))) or "无"))

    lines.append("")
    lines.append("[5] 编译标识与 pak 装配")
    raw = open(elf, "rb").read()
    check("BUILD_HASH = dbf8943（源码 HEAD）", b"dbf8943" in raw)
    check("minarch.elf 与官方不是同一个文件", sha256(elf) != sha256(ref))
    launch = open(os.path.join(a.pak, "launch.sh"), "rb").read()
    check("launch.sh 优先使用 pak 内 minarch.elf", b'MINARCH="$CORES_PATH/minarch.elf"' in launch)
    check("launch.sh 保留系统 elf 回退", b"MINARCH=minarch.elf" in launch)
    cfg = open(os.path.join(a.pak, "default.cfg"), "rb").read()
    check("default.cfg 预设 Aspect + Sharp",
          b"minarch_screen_scaling = Aspect" in cfg and b"minarch_screen_sharpness = Sharp" in cfg)

    lines.append("")
    lines.append("=" * 60)
    lines.append("合计 %d/%d 项通过" % (passed, passed + failed))
    lines.append("=" * 60)

    report = "\n".join(lines) + "\n"
    print(report)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
