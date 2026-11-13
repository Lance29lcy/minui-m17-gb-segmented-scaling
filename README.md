这是一个给 M17 掌机 MinUI 用的 GB.pak。它把 Game Boy 的 160×144 画面显示成 320×272：中间 128 行严格放大 2 倍，上下各 8 行只在横向放大 2 倍、纵向保持 1 倍，左右各留 80 像素黑边。
原版 Aspect 把 144 行拉到 272 行，倍率是 1.8889，最近邻缩放会在整个画面留下粗细不一的细行。这个方案让主体保持方正像素，把失真集中到上下共 16 行。顶部内容会明显被压扁，这是方案本身的取舍，不是故障。
已在 M17 真机验证：pak 能加载、游戏能运行。
使用方法：
1. 从官方 MinUI release v20251127-1 下载 MinUI-20251127-1-base.zip，地址 https://github.com/shauninman/MinUI/releases/tag/v20251127-1 。
2. 把整个 GB.pak 文件夹拷到 SD 卡的 /sdcard/Emus/m17/GB.pak/，文件夹名不要改。里面应该有 launch.sh、default.cfg、gambatte_libretro.so、minarch.elf。
3. 进入 GB 游戏，Menu → Options，把 Screen Scaling 设为 Aspect，Screen Sharpness 设为 Sharp。不要用 Crisp。如果以前手动改过缩放，.userdata 里的 user cfg 会覆盖 default.cfg，需要在菜单里重新选一次 Aspect。
4. 预期画面：x=80..399 是画面区，中间是均匀 2×2 像素，上下各 8 行是 2×1 扁像素。
回滚：删掉 GB.pak/minarch.elf Aspect模式会变为到320*272，横向2倍放大，纵向放大1.88倍且未经处理；删掉整个 GB.pak 文件夹就完全回到原版 MinUI。.system 目录一个字节都没动。
