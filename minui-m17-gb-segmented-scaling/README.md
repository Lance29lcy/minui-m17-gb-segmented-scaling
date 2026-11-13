# MinUI (M17) · GB 8/128/8 分段缩放

给 MinUI / M17 掌机的 Game Boy 模拟增加一个自定义缩放方案：把 GB 原始 **160×144** 画面的**中间 128 行做 2 倍缩放**、**上下各 8 行做 1 倍缩放**，横向始终 2 倍，最终在 **480×272** 屏幕上得到 **320×272** 画面（左右各 80 px 黑边）。

```
源 160×144                          目标 320×272  (x = 80)
┌──────────────┐  8 行  1×       ┌──────────────────────────────┐  8 px   2×1
├──────────────┤ 128 行 2×  →    ├──────────────────────────────┤ 256 px  2×2
├──────────────┤  8 行  1×       ├──────────────────────────────┤  8 px   2×1
└──────────────┘                 └──────────────────────────────┘
                                  8 + 256 + 8 = 272
```

## 为什么这么做

原生 Aspect 模式把 144 行拉到 272 行，纵向倍率 **17/9 ≈ 1.8889**，最近邻会产生 16 条不等高的"细行"，散布整个画面。本方案把失真集中到上下各 8 行（通常是状态栏或画面边缘），换取**中间主体严格 2×2 像素**。

⚠️ 这是明确的取舍：顶部内容（例如菜单第一个选项框）会被明显压扁。它不是"更清晰的全屏方案"，而是"主体像素完美 + 边缘牺牲"的方案。若你更在意顶部，可改用裁掉空白行的方案，但那不属于本仓库范围。

## 状态

| 项目 | 状态 |
|---|---|
| 补丁在干净 `dbf8943` 上应用 / 回滚 | ✅ 已验证 |
| 39 项综合审计、ARM 语法/目标码验证 | ✅ 已验证 |
| 本机 Docker 交叉编译出 `minarch.elf` | ✅ 已验证（72,816 B） |
| 与官方原版 ELF 的 ABI/依赖/符号/反汇编对照 | ✅ 20/20 PASS |
| **M17 真机装卡运行** | ✅ **已实机验证**（2026-11-13，游戏可进入运行，无动态库/符号错误） |
| 分段画面逐像素效果（2×2 / 2×1） | ⏳ 尚无实机截图佐证；"能跑"不等于已逐像素核对 |

## 快速开始

仓库**不含任何上游官方二进制**（见 [LICENSE-NOTICE.md](LICENSE-NOTICE.md)），需要你自行补一个文件。

1. 从官方 [MinUI release `v20251127-1`](https://github.com/shauninman/MinUI/releases/tag/v20251127-1) 下载 `MinUI-20251127-1-base.zip`，从内层的 `MinUI.zip` 取出：

   ```
   .system/m17/cores/gambatte_libretro.so     # 1,139,472 bytes
   ```

   其他版本 / 其他平台的核心**不适用**（脚本会校验大小与指令模式）。

2. 打 4/8 字节 aspect 补丁。**这一步不能省** —— 分段分支的触发条件就是 `aspect_ratio = 320/273`，官方核心报告的是 `10/9`，不打补丁会走原版路径：

   ```sh
   python tools/patch_core.py \
       --input /path/to/gambatte_libretro.so \
       --output GB.pak/gambatte_libretro.so
   ```

   脚本只改 `retro_get_system_av_info()` 里 `movw/movt` 两条立即数，并自检 `w=320 / x=80 / 左右黑边 80/80`。

3. 把整个 `GB.pak/` 拷到 SD 卡：

   ```
   /sdcard/Emus/m17/GB.pak/
   ```

   文件夹名不要改，`EMU_TAG` 决定存档路径。里面应包含 `launch.sh`、`default.cfg`、`gambatte_libretro.so`、`minarch.elf`。

4. 进 GB 游戏 → Menu → Options：

   ```
   Screen Scaling   = Aspect
   Screen Sharpness = Sharp
   ```

   ⚠️ `.userdata` 下的 user cfg 优先级高于 pak 的 `default.cfg`；以前手动改过缩放的话，要在菜单里重新选一次。
   ⚠️ **不要用 Crisp**：它会先 `hard_scale=4` 预放大纹理，源坐标需 ×4，代码故意让 Crisp 走原版路径（不分段）。

5. 预期画面：`x=80..399` 为画面区，中间 `y=8..263` 均匀 2×2，上下各 8 行 2×1 扁像素。

## 它是怎么工作的

- `patches/gb-segmented-8-128-8.patch`：只改 `workspace/m17/platform/platform.c`，**+35 行**。在 `PLAT_flip()` 里对 `160×144 + aspect≈320/273 + Sharp/Soft` 的情况，用三次 `SDL_RenderCopy()` 把三段分别贴到目标矩形，然后 `SDL_RenderPresent()` + 提前返回。原版 Native / Aspect / Fullscreen / Cropped 分支一行未动。
- `GB.pak/minarch.elf`：上述补丁编译出的可执行文件。`launch.sh` 会优先用 pak 自带的 elf，不存在时自动回退系统 `.system/m17/bin/minarch.elf`。
- `GB.pak/` 走 MinUI 原生 pak 机制（`getEmuPath()` 优先查 `/sdcard/Emus/<PLATFORM>/<TAG>.pak/`），**不改 `.system/` 里任何文件**。

## 目录

```
patches/          分段补丁、反向回滚补丁、关闭开关补丁
GB.pak/           可直接拷卡的 pak（缺官方核心，见快速开始）
tools/
  patch_core.py         官方核心 4/8 字节 aspect 补丁 + 自检
  quick-build/          Debian buster armhf 交叉编译镜像与构建脚本
  build-minarch.sh      容器内一键编译
  verify.py             39 项综合审计
  verify_elf.py         与官方 ELF 的 20 项 ABI 核对
  syntax_check.py       从源码提取分支做 ARM 编译验证
实现说明.md       完整技术说明
本机构建说明.md   编译环境、踩坑、复现命令
ELF核对.txt       20/20 对照报告
审计结果.txt / 语法检查.txt
```

> 文档按"本地完整交付包"撰写。凡是提到 `tools/reference/minarch.elf`（官方原版对照 ELF）或构建日志的地方，都是本仓库刻意剔除的文件；如需复跑 `verify_elf.py` / `verify.py`，请自行从官方 release 取回对应文件放到指定路径。

## 自行编译

```sh
# 1) 干净 MinUI 源码，HEAD dbf8943
git clone https://github.com/shauninman/MinUI.git && git checkout dbf8943
git apply /path/to/patches/gb-segmented-8-128-8.patch

# 2) 本机 Docker（已验证：Docker Desktop + debian/eol:buster-slim）
docker build -t m17-quick tools/quick-build
# 详见 tools/quick-build/build-inside.sh 与 本机构建说明.md
```

产物 `minarch.elf` 为 ELF32 / ARM / hard-float / EXEC，与官方 `v20251127-1` 的 9 个 `DT_NEEDED`、`PT_INTERP`、`GLIBC_2.4/2.7` 需求一致，未定义符号无新增。设备 glibc 2.26 可加载，已实机验证。

## 回滚

| 目的 | 做法 |
|---|---|
| 回到上一版 Aspect + nearest 1.8889× | 删掉 `GB.pak/minarch.elf`，`launch.sh` 自动用系统原版 |
| 完全回到原版 MinUI | 删掉 `/sdcard/Emus/m17/GB.pak/` |

`.system/` 下一个字节都没有动过。

## 来源与授权

见 [LICENSE-NOTICE.md](LICENSE-NOTICE.md)。上游 [shauninman/MinUI](https://github.com/shauninman/MinUI) 在 `dbf8943` 时**未附带 LICENSE 文件**，因此本仓库不收录其官方二进制与源码副本，仅保留 diff、自行编写的脚本与文档，以及一个从上游源码编译的 `minarch.elf`。
