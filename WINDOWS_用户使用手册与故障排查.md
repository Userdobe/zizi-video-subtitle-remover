# 字字动画视频去字幕工具
## Windows 用户使用手册与常见问题排查指南

> 适用版本：当前项目中的批量去字幕 GUI、Inpainting 修复和运动字幕跟踪工具
>
> 适用系统：Windows 10、Windows 11 64 位

---

## 目录

1. [软件功能概览](#1-软件功能概览)
2. [文件结构](#2-文件结构)
3. [运行方式选择](#3-运行方式选择)
4. [首次安装环境](#4-首次安装环境)
5. [直接运行 Python 程序](#5-直接运行-python-程序)
6. [批量去字幕 GUI 使用方法](#6-批量去字幕-gui-使用方法)
7. [运动字幕 GUI 使用方法](#7-运动字幕-gui-使用方法)
8. [字幕区域设置](#8-字幕区域设置)
9. [修复算法选择](#9-修复算法选择)
10. [OCR 自动检测配置](#10-ocr-自动检测配置)
11. [批量命令行使用](#11-批量命令行使用)
12. [打包成独立 EXE](#12-打包成独立-exe)
13. [效果调优建议](#13-效果调优建议)
14. [常见问题排查](#14-常见问题排查)
15. [性能与资源建议](#15-性能与资源建议)
16. [已知限制](#16-已知限制)
17. [安全、许可证与文件备份](#17-安全许可证与文件备份)

---

## 1. 软件功能概览

本项目用于处理 MiniMax H3 等视频生成模型产生的视频字幕，支持固定字幕、轻微移动字幕以及部分运动画面。

### 1.1 固定字幕处理

适合以下情况：

- 字幕始终在画面底部；
- 字幕区域基本不移动；
- 视频数量较多，需要批量处理；
- 更重视速度和简单操作。

可使用：

- `batch_remove_gui.py`
- `batch_remove_subtitles.py`
- `delogo` 算法
- `telea` 或 `ns` Inpainting 算法

### 1.2 运动字幕处理

适合以下情况：

- 字幕位置会随镜头或画面移动；
- 视频存在轻微推拉、平移或运动；
- 固定坐标遮罩无法覆盖字幕全程；
- 需要 OCR 与光流跟踪自动更新字幕框。

可使用：

- `tracked_inpaint_gui.py`
- `tracked_inpaint_remove.py`
- OCR 初始定位
- Lucas-Kanade 光流跟踪
- Telea Inpainting 修复
- 定期 OCR 重新校正
- 场景切换检测

### 1.3 重要说明

本工具的传统 Inpainting 会根据字幕周围的画面内容进行估算。如果字幕覆盖了人物脸部、手部或复杂运动物体，程序无法准确恢复被遮挡的真实内容，可能出现模糊、拖影或纹理不连续。

---

## 2. 文件结构

建议将项目文件放在一个独立目录，例如：

```text
D:\字字动画去字幕工具\
├─ subtitle_remover.py                         # 单视频基础 GUI
├─ batch_remove_subtitles.py                   # 批量命令行脚本
├─ batch_remove_gui.py                          # 批量处理 GUI
├─ tracked_inpaint_remove.py                    # 运动字幕处理引擎
├─ tracked_inpaint_gui.py                       # 运动字幕 GUI
├─ requirements_inpainting.txt                  # Inpainting 依赖
├─ requirements_tracking.txt                    # OCR/光流处理依赖
├─ 启动去字幕工具.bat                           # 单视频 GUI 启动
├─ 启动批量去字幕GUI.bat                         # 批量 GUI 启动
├─ 启动运动字幕GUI.bat                          # 运动字幕 GUI 启动
├─ 打包批量GUI为EXE.bat                         # 批量 GUI 打包
├─ 打包运动字幕GUI为EXE.bat                     # 运动字幕 GUI 打包
└─ README.md
```

如果使用打包后的版本，建议每个 EXE 使用一个独立文件夹，不要只复制单个 `.exe` 文件。

---

## 3. 运行方式选择

| 使用场景 | 推荐方式 |
|---|---|
| 只处理一个固定字幕视频 | 单视频 GUI |
| 一次处理多个固定区域字幕视频 | 批量去字幕 GUI |
| 字幕位置会移动 | 运动字幕 GUI |
| 熟悉命令行、需要自动化 | Python 命令行脚本 |
| 目标电脑没有 Python | 打包后的 EXE |
| 追求最快速度 | `delogo` |
| 追求更自然背景 | `telea` |
| 背景渐变、希望更平滑 | `ns` |

---

## 4. 首次安装环境

### 4.1 安装 Python

如果准备直接运行 `.py` 文件，需要安装 Python 3.10 或更高版本。

1. 打开 Python 官网：<https://www.python.org/downloads/windows/>
2. 下载 Windows 64 位安装程序；
3. 安装首页勾选：

```text
Add Python to PATH
```

4. 安装完成后打开命令提示符，执行：

```bat
python --version
```

正常情况下会看到类似：

```text
Python 3.11.9
```

### 4.2 安装 FFmpeg

FFmpeg 负责：

- 读取视频；
- 输出 H.264 视频；
- 合并原始音频；
- 生成预览帧。

安装后需要确保以下命令可用：

```bat
ffmpeg -version
ffprobe -version
```

如果不想配置系统 PATH，也可以把以下文件放到项目目录：

```text
ffmpeg.exe
ffprobe.exe
```

### 4.3 安装 OpenCV 与 NumPy

如果只使用 `delogo`，可以不安装 OpenCV。

如果要使用 `telea`、`ns` 或运动字幕跟踪，执行：

```bat
python -m pip install -r requirements_tracking.txt
```

或者手动安装：

```bat
python -m pip install opencv-python numpy
```

### 4.4 安装 Tesseract OCR

OCR 自动检测和运动字幕跟踪需要 Tesseract。

推荐下载 Windows 发行版：

<https://github.com/UB-Mannheim/tesseract/wiki>

安装时建议包含：

- English；
- Simplified Chinese / `chi_sim`；
- Tesseract 命令行工具。

安装后检查：

```bat
tesseract --version
tesseract --list-langs
```

如果语言列表中出现：

```text
chi_sim
eng
```

说明中文 OCR 环境基本正常。

如果 Tesseract 没有加入 PATH，可以在 GUI 中选择 `tesseract.exe` 的完整路径，例如：

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## 5. 直接运行 Python 程序

在项目目录空白处按住 Shift，右键选择“在此处打开 PowerShell 窗口”，或先执行：

```bat
cd /d "D:\字字动画去字幕工具"
```

### 5.1 启动单视频 GUI

```bat
python subtitle_remover.py
```

也可以双击：

```text
启动去字幕工具.bat
```

### 5.2 启动批量 GUI

```bat
python batch_remove_gui.py
```

也可以双击：

```text
启动批量去字幕GUI.bat
```

### 5.3 启动运动字幕 GUI

```bat
python tracked_inpaint_gui.py
```

也可以双击：

```text
启动运动字幕GUI.bat
```

---

## 6. 批量去字幕 GUI 使用方法

### 6.1 选择输入文件夹

1. 点击“输入文件夹”旁边的“浏览”；
2. 选择包含视频的文件夹；
3. 支持的格式包括：

```text
.mp4 .mov .mkv .avi .webm .m4v .ts .flv
```

### 6.2 选择输出文件夹

建议将输出文件夹设置为不同于输入文件夹的目录，例如：

```text
输入：D:\videos
输出：D:\videos_output
```

程序默认会生成类似：

```text
原视频.mp4
原视频_去字幕.mp4
```

### 6.3 是否扫描子文件夹

勾选“包含子文件夹”后，程序会递归扫描输入目录，并在输出目录中保留相同的子目录结构。

### 6.4 选择字幕区域

有三种模式：

- OCR 自动检测；
- 自动使用底部字幕区域；
- 手动像素区域。

建议先选择“自动使用底部字幕区域”测试效果，再根据结果选择 OCR 或手动区域。

### 6.5 选择修复算法

GUI 中的算法选择如下：

- `delogo`：速度快，适合简单背景；
- `telea`：通常更自然，建议优先使用；
- `ns`：更平滑，但速度较慢。

### 6.6 开始处理

点击“开始批量处理”后，右侧日志会显示：

- 找到的视频数量；
- 当前处理文件；
- 当前区域坐标；
- 处理成功或失败信息；
- 最终统计结果。

处理期间不要移动输入文件、输出文件夹或关闭窗口。

---

## 7. 运动字幕 GUI 使用方法

运动字幕 GUI 适合单个视频，处理步骤如下：

### 7.1 选择视频

在“输入视频”中选择原始视频，在“输出视频”中选择新的输出文件名。

不要让输出路径与输入路径相同。

### 7.2 设置 Tesseract 路径

如果已经执行：

```bat
tesseract --version
```

且命令正常，可以留空。

否则点击浏览，选择：

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 7.3 参数建议

第一次使用建议保持默认值：

| 参数 | 推荐值 |
|---|---:|
| OCR 语言 | `chi_sim+eng` |
| OCR 重检测间隔 | `8` |
| 光流置信度 | `0.35` |
| 场景切换阈值 | `35` |
| Inpainting 半径 | `3` |
| 遮罩外扩像素 | `2` |

### 7.4 参数调节

如果字幕移动较快：

```text
OCR 重检测间隔：4 或 5
```

如果字幕边缘残留：

```text
遮罩外扩像素：3 或 4
```

如果背景变得过于模糊：

```text
遮罩外扩像素：1
Inpainting 半径：2
```

如果镜头切换后跟踪错误：

```text
场景切换阈值：25
```

### 7.5 处理日志

运动字幕工具会显示：

- OCR 重新定位次数；
- 当前字幕框坐标；
- 光流跟踪失败信息；
- 当前处理进度；
- 最终处理帧数和耗时。

---

## 8. 字幕区域设置

### 8.1 固定像素区域格式

格式为：

```text
x,y,w,h
```

例如：

```text
80,720,1120,180
```

含义：

- `x=80`：左边界；
- `y=720`：上边界；
- `w=1120`：区域宽度；
- `h=180`：区域高度。

坐标原点位于视频左上角。

### 8.2 自动底部区域

默认区域大致为：

```text
左边界：4%
上边界：76%
宽度：92%
高度：20%
```

优点是无需知道视频分辨率，程序会按每个视频尺寸计算。

### 8.3 手动区域建议

遮罩应覆盖：

- 字幕文字本身；
- 字幕描边；
- 少量上下左右边缘。

不要无目的地覆盖整条画面，否则 Inpainting 会修复过大区域，容易造成明显模糊。

---

## 9. 修复算法选择

### 9.1 `delogo`

优点：

- 不需要 OpenCV；
- 速度最快；
- 内存占用较低；
- 适合简单背景。

缺点：

- 复杂背景效果有限；
- 人物和纹理区域可能出现模糊。

### 9.2 `telea`

优点：

- 速度和效果平衡较好；
- 通常比 `delogo` 更自然；
- 适合天空、墙面、地面等纹理背景。

缺点：

- 逐帧处理速度较慢；
- 对大面积字幕遮挡有限；
- 需要 OpenCV 和 NumPy。

### 9.3 `ns`

优点：

- 修复结果更平滑；
- 对渐变背景有时更合适。

缺点：

- 通常比 Telea 更慢；
- 细节恢复不一定优于 Telea。

### 9.4 推荐试用顺序

```text
先试 delogo
    ↓
效果不自然时试 telea
    ↓
背景渐变明显时试 ns
```

---

## 10. OCR 自动检测配置

### 10.1 OCR 的工作方式

程序会：

1. 从视频中抽取采样帧；
2. 让 Tesseract 识别文字；
3. 过滤画面下半部分的文字；
4. 合并文字框；
5. 扩展少量边缘；
6. 生成字幕修复区域。

### 10.2 OCR 识别不到字幕

可能原因：

- 字幕字体过小；
- 字幕是艺术字体或发光字体；
- 字幕颜色和背景对比度过低；
- 未安装 `chi_sim`；
- Tesseract 路径未配置；
- 字幕不在画面下半部分。

解决方法：

1. 检查：

```bat
tesseract --list-langs
```

2. 确认有 `chi_sim`；
3. 在 GUI 中手动选择 Tesseract 路径；
4. 使用“自动底部字幕区域”；
5. 改用手动区域；
6. 适当调低 OCR 置信度。

### 10.3 OCR 误识别画面文字

如果画面中有招牌、路牌或标题，可能被误判为字幕。

可尝试：

- 提高 OCR 搜索起始比例，例如 `0.60`；
- 使用“手动像素区域”；
- 缩小 OCR 搜索区域；
- 按场景分段处理。

---

## 11. 批量命令行使用

### 11.1 默认批量处理

```bat
python batch_remove_subtitles.py "D:\videos" --recursive
```

默认输出到：

```text
D:\videos_output
```

### 11.2 指定输出文件夹

```bat
python batch_remove_subtitles.py "D:\videos" ^
  -o "D:\videos_clean" ^
  --recursive
```

### 11.3 使用 Telea Inpainting

```bat
python batch_remove_subtitles.py "D:\videos" ^
  -o "D:\videos_clean" ^
  --recursive ^
  --method telea
```

### 11.4 固定像素区域

```bat
python batch_remove_subtitles.py "D:\videos" ^
  --recursive ^
  --region 80,720,1120,180 ^
  --method telea
```

### 11.5 覆盖已有输出

```bat
python batch_remove_subtitles.py "D:\videos" ^
  --recursive ^
  --overwrite
```

### 11.6 快速模式

```bat
python batch_remove_subtitles.py "D:\videos" ^
  --recursive ^
  --fast
```

### 11.7 运动字幕脚本

```bat
python tracked_inpaint_remove.py ^
  "D:\input\video.mp4" ^
  "D:\output\video_clean.mp4" ^
  --redetect-interval 8 ^
  --flow-confidence 0.35 ^
  --scene-threshold 35 ^
  --inpaint-radius 3 ^
  --mask-dilate 2
```

---

## 12. 打包成独立 EXE

### 12.1 打包批量 GUI

在 Windows 项目目录中双击：

```text
打包批量GUI为EXE.bat
```

生成目录：

```text
dist\字字动画批量去字幕GUI\
```

主要文件：

```text
字字动画批量去字幕GUI.exe
字字动画批量去字幕.exe
```

### 12.2 打包运动字幕 GUI

双击：

```text
打包运动字幕GUI为EXE.bat
```

生成目录：

```text
dist\字字动画运动字幕GUI\
```

主要文件：

```text
字字动画运动字幕GUI.exe
字字动画运动字幕修复.exe
```

### 12.3 发布时必须复制的文件

推荐保留整个文件夹，而不是只复制 EXE：

```text
字字动画运动字幕GUI\
├─ 字字动画运动字幕GUI.exe
├─ 字字动画运动字幕修复.exe
├─ ffmpeg.exe
└─ ffprobe.exe
```

### 12.4 目标电脑的额外依赖

打包后通常不需要：

- Python；
- OpenCV；
- NumPy。

但运动字幕 OCR 仍然需要：

- Tesseract OCR；
- `chi_sim` 中文语言包。

### 12.5 打包失败时的注意事项

- 使用 Windows 电脑打包，不建议跨平台直接生成 Windows EXE；
- 确保 Python、PyInstaller 正常；
- 确保项目路径不要包含过长路径；
- 确保杀毒软件没有拦截 PyInstaller 临时文件；
- 打包完成后不要只复制主 GUI EXE。

---

## 13. 效果调优建议

### 13.1 先做短片测试

不要一开始处理一小时视频。建议：

1. 截取 5～10 秒测试片段；
2. 使用相同字幕位置和算法；
3. 对比输出效果；
4. 确认参数后再批量处理。

### 13.2 遮罩大小优先于算法

如果效果不好，优先检查字幕框：

- 字幕没有完全覆盖：扩大 2～5 个像素；
- 背景变得太模糊：缩小遮罩；
- 修复边缘明显：适当增加 `mask-dilate`；
- 整个底部被模糊：不要直接覆盖过大的 20% 区域。

### 13.3 不同视频分开处理

如果视频的：

- 分辨率不同；
- 字幕位置不同；
- 字幕大小不同；
- 横屏和竖屏混合；

建议按类型分成多个文件夹处理。

### 13.4 复杂视频建议使用运动模式

固定区域模式不适合：

- 字幕从底部移动到中部；
- 摄像机快速运动；
- 字幕跟随人物或物体；
- 镜头频繁切换。

此时优先使用运动字幕 GUI。

---

## 14. 常见问题排查

### 14.1 双击 BAT 后窗口一闪而过

排查方法：

1. 打开命令提示符；
2. 进入项目目录：

```bat
cd /d "D:\字字动画去字幕工具"
```

3. 手动执行 BAT 中的 Python 命令，例如：

```bat
python batch_remove_gui.py
```

这样可以看到完整错误信息。

### 14.2 提示“找不到 Python”

执行：

```bat
python --version
```

如果失败：

- 重新安装 Python；
- 勾选 `Add Python to PATH`；
- 重启命令提示符；
- 或使用完整路径运行 Python。

### 14.3 提示“找不到 ffmpeg 或 ffprobe”

检查：

```bat
ffmpeg -version
ffprobe -version
```

解决方案：

- 把 FFmpeg 的 `bin` 目录加入 PATH；或
- 将 `ffmpeg.exe`、`ffprobe.exe` 放到程序同目录；或
- 命令行使用 `--ffmpeg` 和 `--ffprobe` 指定完整路径。

### 14.4 提示“找不到 Tesseract OCR”

检查：

```bat
tesseract --version
```

如果失败：

- 安装 Tesseract；
- 加入 PATH；或
- 在 GUI 中手动选择 `tesseract.exe`。

### 14.5 OCR 语言错误

检查：

```bat
tesseract --list-langs
```

如果没有 `chi_sim`：

- 安装中文语言包；
- 或将语言参数改为：

```text
eng
```

但中文识别效果会明显下降。

### 14.6 提示缺少 OpenCV 或 NumPy

执行：

```bat
python -m pip install -r requirements_tracking.txt
```

或者：

```bat
python -m pip install opencv-python numpy
```

如果使用的是打包 EXE，重新运行打包脚本，不要直接把开发机的 Python 包复制到目标电脑。

### 14.7 视频能打开，但处理失败

常见原因：

- 输入文件损坏；
- 视频编码格式不兼容；
- 输出路径没有写入权限；
- 输出文件正在被播放器占用；
- 磁盘空间不足；
- 视频路径包含特殊字符导致外部工具异常。

排查步骤：

1. 用 FFmpeg 检查视频：

```bat
ffprobe "D:\videos\input.mp4"
```

2. 尝试复制视频到短路径，例如：

```text
D:\test\input.mp4
```

3. 关闭正在播放输出文件的播放器；
4. 检查磁盘空间；
5. 先处理 5 秒短视频测试。

### 14.8 输出视频没有声音

程序会尝试保留原始音频，但以下情况可能没有声音：

- 原视频本身没有音轨；
- 输入音频编码异常；
- 音频流无法被 FFmpeg 读取；
- 输出容器不支持原始音频格式；
- 处理中途被强制关闭。

可以用以下命令检查原视频是否有音频：

```bat
ffprobe -select_streams a -show_streams "D:\videos\input.mp4"
```

### 14.9 字幕没有完全去除

尝试：

- 增大遮罩区域；
- 增加 `--mask-dilate`；
- 重新检查 OCR 语言；
- 降低 OCR 置信度；
- 减小 OCR 重检测间隔；
- 改用 Telea 或 NS；
- 使用手动区域进行测试。

### 14.10 输出画面出现大面积模糊

通常说明遮罩太大。

建议：

```text
减少遮罩高度
减少遮罩外扩像素
Inpainting 半径改为 2
尝试 Telea 而不是 NS
```

### 14.11 字幕移动后跟踪错位

建议：

```text
降低 OCR 重检测间隔，例如 8 改为 4
降低光流置信度阈值，例如 0.35 改为 0.25
降低场景切换阈值，例如 35 改为 25
```

如果仍不稳定，说明字幕运动幅度过大或背景缺少可跟踪特征，应按镜头切分处理。

### 14.12 镜头切换后画面被错误修复

尝试降低：

```text
--scene-threshold 25
```

这样会更敏感地识别镜头变化，并强制重新 OCR。

### 14.13 运行速度很慢

原因通常是：

- 使用了 Inpainting；
- 每几帧就 OCR；
- 视频分辨率很高；
- CPU 性能较弱；
- 输出使用高质量编码。

解决方法：

- 增大 `--redetect-interval`；
- 使用 `delogo`；
- 使用 `--fast`；
- 使用较快的 `--preset veryfast` 或 `ultrafast`；
- 先降低视频分辨率测试。

### 14.14 打包后提示找不到处理引擎

确认 GUI 文件夹中同时存在：

```text
字字动画运动字幕GUI.exe
字字动画运动字幕修复.exe
```

如果缺少第二个文件，请重新执行：

```text
打包运动字幕GUI为EXE.bat
```

### 14.15 打包后提示找不到 FFmpeg

确认以下文件与 EXE 位于同一目录：

```text
ffmpeg.exe
ffprobe.exe
```

如果打包脚本没有自动复制它们，请手动复制。

### 14.16 Windows Defender 或杀毒软件报警

PyInstaller 生成的 EXE 有时会被部分安全软件误报，尤其是未签名的单文件程序。

建议：

- 使用 `--onedir` 目录模式；
- 从可信来源获取 FFmpeg 和 Tesseract；
- 在内部网络中分发时进行代码签名；
- 不要关闭系统安全防护后运行来源不明的文件。

---

## 15. 性能与资源建议

### 15.1 内存

OpenCV 会逐帧处理视频，但高分辨率视频仍然需要较多内存。

建议：

- 4K 视频先用短片测试；
- 同时只运行一个任务；
- 关闭大型视频编辑软件；
- 保证输出磁盘空间充足。

### 15.2 CPU

Telea、NS 和 OCR 都主要消耗 CPU。处理时间可能接近或超过视频时长，具体取决于：

- 视频分辨率；
- 帧率；
- OCR 频率；
- 遮罩面积；
- CPU 型号。

### 15.3 磁盘

处理过程中会生成临时视频，至少预留：

- 原视频大小的 2 倍空间；
- 4K 视频建议预留更多空间。

不要在系统盘空间不足时批量处理大量视频。

---

## 16. 已知限制

当前版本存在以下限制：

1. OCR 对艺术字体、低对比度字幕和复杂特效字幕的识别可能不稳定；
2. 普通 Inpainting 不能准确恢复被字幕完全遮挡的人物细节；
3. 光流需要画面中有足够纹理或边缘特征；
4. 快速镜头切换可能导致跟踪短暂失败；
5. 批量 OCR 检测通常使用第一个视频确定区域，不同分辨率视频建议分组；
6. Tesseract OCR 需要单独安装语言包；
7. 当前版本未集成 GPU 加速的视频级 AI 修复模型；
8. 输出视频会重新编码，无法做到完全无损复制画面。

---

## 17. 安全、许可证与文件备份

### 17.1 永远不要覆盖原视频

建议输出到独立目录：

```text
D:\videos_original
D:\videos_clean
```

不要使用与输入文件相同的输出路径。

### 17.2 先备份重要视频

在批量处理前，建议先备份原始视频。尤其是使用 `--overwrite` 时，输出文件可能替换已有结果。

### 17.3 第三方软件许可证

本项目会调用：

- FFmpeg；
- Tesseract OCR；
- OpenCV；
- NumPy；
- PyInstaller。

这些软件分别遵循各自的开源许可证。正式分发 EXE 时，请保留相应许可证和版权说明，并按照相关许可证要求分发 FFmpeg、Tesseract 等组件。

### 17.4 建议的首次测试流程

```text
1. 准备一个 5～10 秒视频片段
2. 使用 delogo 测试
3. 使用 telea 测试
4. 检查音频和画面比例
5. 检查字幕边缘
6. 调整遮罩和修复半径
7. 再开始批量处理
```

---

## 快速检查清单

运行前：

- [ ] 输入视频可以正常播放；
- [ ] 输出目录不是输入目录；
- [ ] FFmpeg 可用；
- [ ] 使用 OCR 时 Tesseract 可用；
- [ ] 使用 Inpainting 时 OpenCV 和 NumPy 已安装；
- [ ] 硬盘空间足够；
- [ ] 已备份原视频。

运行后：

- [ ] 输出视频可以播放；
- [ ] 原音频存在；
- [ ] 字幕已移除；
- [ ] 没有大面积异常模糊；
- [ ] 镜头切换处没有明显错误；
- [ ] 输出文件数量与输入文件数量一致。
