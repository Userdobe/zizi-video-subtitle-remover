# 字字动画 · 视频去字幕工具

一个面向 Windows 的本地视频去字幕工具，适合处理 Mini Max H3 生成视频中常见的固定位置字幕。

## 已实现功能

- 选择 MP4、MOV、MKV、AVI、WebM、M4V 视频
- 首帧预览
- 一键推荐底部字幕区域
- 在画面上拖动框选字幕区域
- 坐标可手工微调
- 使用 FFmpeg `delogo` 局部修复，保留视频画面比例
- 保留原视频音轨并导出 H.264 MP4
- 显示处理进度
- 完全本地运行，不上传视频

## Windows 使用方式

### 方式一：直接运行

1. 安装 [Python 3.10+](https://www.python.org/downloads/windows/)，安装时勾选 **Add Python to PATH**。
2. 安装 [FFmpeg](https://ffmpeg.org/download.html)，确保 `ffmpeg.exe` 和 `ffprobe.exe` 可以在命令行找到；也可以直接把这两个文件放到 `subtitle_remover.py` 同目录。
3. 双击 `启动去字幕工具.bat`。
4. 选择视频，点击“智能推荐底部字幕区”或直接在左侧画面拖框。
5. 点击“开始去字幕并导出”。

### 方式二：打包成 exe

双击 `打包为EXE.bat`。打包后，把 `ffmpeg.exe` 和 `ffprobe.exe` 复制到：

```text
dist/字字动画去字幕/
```

然后双击 `字字动画去字幕.exe` 即可运行。FFmpeg 需要遵循其许可证要求，建议使用官方或可信发行版。

## 效果说明

当前版本针对**固定位置、固定字幕条**做局部修复。FFmpeg 的 `delogo` 会根据字幕周边像素进行插值，因此：

- 纯背景、墙面、天空、地面等区域通常效果较好；
- 字幕压在人物脸部、手部或复杂运动物体上时，可能留下模糊/拖影；
- 若字幕有多个区域，需要分别处理或后续增加多区域遮罩；
- 若字幕随画面移动，需要增加跟踪遮罩，当前版本尚未实现。

## 后续建议

1. 增加多区域字幕框。
2. 增加时间段设置，只处理字幕出现的区间。
3. 增加运动跟踪与关键帧遮罩。
4. 接入 LaMa / ProPainter 等 AI 修复模型，改善人物和复杂背景上的效果。
5. 增加批量处理和预览对比。


## 批量处理多个视频

新增脚本：`batch_remove_subtitles.py`。它只依赖 Python 标准库和 FFmpeg，不需要安装 OpenCV。

### 基本用法

在命令提示符中运行：

```bat
python batch_remove_subtitles.py "D:\\videos" --recursive
```

默认会在输入文件夹旁创建 `videos_output` 文件夹，输出文件名类似：

```text
原视频.mp4 → 原视频_去字幕.mp4
```

也可以指定输出目录：

```bat
python batch_remove_subtitles.py "D:\\videos" -o "D:\\videos_clean" --recursive
```

### 固定像素区域

如果所有视频分辨率相同，并且已经知道字幕区域，例如 `x=80,y=720,w=1120,h=180`：

```bat
python batch_remove_subtitles.py "D:\\videos" --recursive --region 80,720,1120,180
```

### 默认比例区域

未指定 `--region` 时，脚本会按每个视频的尺寸自动计算区域：

- 左边界：4%
- 上边界：76%
- 区域宽度：92%
- 区域高度：20%

可以按需调整：

```bat
python batch_remove_subtitles.py "D:\\videos" --recursive --left 0.02 --top 0.72 --region-width 0.96 --region-height 0.24
```

### 其他常用参数

```bat
REM 覆盖已经存在的输出文件
python batch_remove_subtitles.py "D:\\videos" --recursive --overwrite

REM 快速模式，编码速度更快、文件更小，但画质略有损失
python batch_remove_subtitles.py "D:\\videos" --recursive --fast

REM 指定 FFmpeg 路径
python batch_remove_subtitles.py "D:\\videos" --recursive --ffmpeg "C:\\ffmpeg\\bin\\ffmpeg.exe" --ffprobe "C:\\ffmpeg\\bin\\ffprobe.exe"
```

也可以把输入文件夹拖到 `批量去字幕.bat` 上运行；如果需要指定输出目录，可在命令行中执行：

```bat
批量去字幕.bat "D:\\videos" "D:\\videos_output"
```


## 批量处理图形界面

新增：`batch_remove_gui.py`，可以通过鼠标操作：

1. 选择输入文件夹和输出文件夹；
2. 勾选是否扫描子文件夹；
3. 选择字幕区域方式；
4. 点击“开始批量处理”；
5. 在右侧日志查看每个视频的处理状态。

双击 `启动批量去字幕GUI.bat` 即可运行。

## 字幕区域自动检测

GUI 提供三种方式：

- **OCR 自动检测（推荐）**：从第一个视频抽取 3 个采样帧，使用 Tesseract OCR 识别下半部分文字，再自动生成修复区域；
- **自动使用底部字幕区域**：不安装 OCR 也能使用，默认覆盖画面底部 20%；
- **手动像素区域**：适合字幕位置固定且视频分辨率一致的批量任务。

OCR 是可选功能。安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) 后，确保 `tesseract.exe` 已加入 PATH，GUI 就会自动启用 OCR；没有 Tesseract 时会自动回退到底部区域，不影响批量处理。

注意：OCR 检测使用第一个视频的区域作为整批视频的区域。如果同一批视频分辨率不同，建议使用“自动使用底部字幕区域”，或者按分辨率分组处理。

## 打包成独立 Windows EXE

### 方式一：使用打包脚本

双击 `打包批量GUI为EXE.bat`。它会安装 PyInstaller 并生成：

```text
dist/字字动画批量去字幕GUI/字字动画批量去字幕GUI.exe
```

如果 `ffmpeg.exe` 和 `ffprobe.exe` 位于项目目录，打包脚本会自动复制它们到 EXE 文件夹。

### 方式二：命令行手动打包

```bat
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --windowed --name 字字动画批量去字幕GUI --add-data "batch_remove_subtitles.py;." batch_remove_gui.py
```

为了让没有 Python 的电脑也能运行，还需要把以下文件放进 `dist\\字字动画批量去字幕GUI\\`：

```text
ffmpeg.exe
ffprobe.exe
```

推荐使用 `--onedir` 而不是 `--onefile`，启动更快，也方便放置 FFmpeg。最终把整个 `dist\\字字动画批量去字幕GUI` 文件夹复制到目标电脑，双击其中的 EXE 即可。


## Inpainting 图像修复模式

现在批量脚本和 GUI 支持三种修复算法：

| 模式 | 特点 | 适用情况 |
|---|---|---|
| `delogo` | FFmpeg 原生滤镜，速度最快 | 字幕压在简单背景上，追求速度 |
| `telea` | OpenCV 快速行进法 Inpainting，纹理细节通常更自然 | 推荐默认尝试，适合墙面、天空、地面等背景 |
| `ns` | OpenCV Navier-Stokes 修复，结果更平滑 | 背景渐变明显、希望画面更柔和 |

命令行使用示例：

```bat
python -m pip install -r requirements_inpainting.txt
python batch_remove_subtitles.py "D:\\videos" -o "D:\\videos_clean" --recursive --method telea
```

如果字幕区域是 `80,720,1120,180`：

```bat
python batch_remove_subtitles.py "D:\\videos" --recursive --region 80,720,1120,180 --method telea
```

修复半径默认为 `3.0`，复杂背景可以尝试：

```bat
python batch_remove_subtitles.py "D:\\videos" --recursive --method telea --inpaint-radius 4
```

在 GUI 的“修复算法”下拉框中选择 `telea` 或 `ns` 即可。Inpainting 会逐帧读取并处理视频，再用 FFmpeg 合回原音频，所以比 `delogo` 更慢，也会消耗更多内存和 CPU。

### 效果调优建议

1. **遮罩不要过大**：尽量只覆盖字幕文字，再留少量边缘；默认底部 20% 区域适合快速测试，但不是最精细的遮罩。
2. **先试 `telea`**：通常在自然纹理背景上细节更好。
3. **人物或复杂运动背景**：Inpainting 也不能凭空恢复被字幕完全遮挡的真实内容，可能需要更高级的视频修复模型或运动跟踪遮罩。
4. **字幕移动时**：当前版本仍使用固定区域；应先按场景分段，或后续加入关键帧/目标跟踪。


## 运动字幕自动跟踪脚本

新增 `tracked_inpaint_remove.py`，用于字幕位置随镜头或画面变化的视频，处理链路为：

```text
Tesseract OCR 初始检测
    ↓
Lucas-Kanade 稀疏光流逐帧跟踪
    ↓
每 N 帧 OCR 重新校正
    ↓
场景切换强制重新检测
    ↓
Telea Inpainting 逐帧修复
    ↓
FFmpeg 合并原音频
```

### 安装依赖

```bat
python -m pip install -r requirements_tracking.txt
```

另外需要安装：

- FFmpeg，并确保 `ffmpeg.exe`、`ffprobe.exe` 在 PATH 中；
- Tesseract OCR，并确保 `tesseract.exe` 在 PATH 中；
- Tesseract 中文语言包 `chi_sim`，否则可使用 `--language eng`。

### 基本用法

```bat
python tracked_inpaint_remove.py "D:\\input\\video.mp4" "D:\\output\\video_clean.mp4"
```

### 推荐参数

```bat
python tracked_inpaint_remove.py "D:\\input\\video.mp4" "D:\\output\\video_clean.mp4" ^
  --redetect-interval 8 ^
  --flow-confidence 0.35 ^
  --scene-threshold 35 ^
  --inpaint-radius 3 ^
  --mask-dilate 2
```

参数说明：

| 参数 | 作用 | 默认值 |
|---|---|---:|
| `--redetect-interval` | 每隔多少帧重新 OCR | `8` |
| `--search-top` | OCR 搜索画面下方区域的起始比例 | `0.50` |
| `--flow-window` | Lucas-Kanade 搜索窗口 | `21` |
| `--flow-levels` | 光流金字塔层数 | `3` |
| `--flow-confidence` | 光流置信度低于此值时重新 OCR | `0.35` |
| `--scene-threshold` | 场景切换阈值，越小越敏感 | `35` |
| `--inpaint-radius` | Telea 修复半径 | `3` |
| `--mask-dilate` | 字幕遮罩外扩像素 | `2` |

### 调参建议

- 字幕运动较快：把 `--redetect-interval` 调到 `4` 或 `5`；
- 字幕位置变化较慢：可以调到 `10` 或 `12`，减少 OCR 次数；
- OCR 框偏小、残留字幕边缘：增加 `--mask-dilate 3` 或 `4`；
- 修复区域发糊：减小 `--mask-dilate` 和 `--inpaint-radius`；
- 场景切换后跟踪跳动：降低 `--scene-threshold`，例如设置为 `25`；
- OCR 把画面中部招牌识别成字幕：提高 `--search-top`，例如设置为 `0.60`。

脚本在 OCR 未识别到字幕时会保留原始帧，在光流跟踪失败时会等待下一帧重新 OCR，避免把错误区域长时间涂抹。对于字幕覆盖人物、快速运动物体或复杂场景，建议后续使用视频级 AI 修复模型进一步提升效果。


## 运动字幕 GUI 与 Windows EXE

新增：`tracked_inpaint_gui.py`，用于单个运动字幕视频的鼠标操作处理。双击 `启动运动字幕GUI.bat` 可以直接启动。

GUI 可选择：

- 输入视频和输出视频；
- Tesseract OCR 路径；
- OCR 语言；
- OCR 重新检测间隔；
- 光流置信度；
- 场景切换阈值；
- Telea 修复半径；
- 遮罩外扩像素。

### 打包成 Windows EXE

在 Windows 上双击：

```text
打包运动字幕GUI为EXE.bat
```

脚本会生成两个程序：

```text
字字动画运动字幕GUI.exe   # 图形界面
字字动画运动字幕修复.exe  # OCR/光流/Inpainting 处理引擎
```

GUI EXE 会自动调用同目录下的处理引擎，所以发布时必须保留整个目录结构：

```text
dist\\字字动画运动字幕GUI\\
├─ 字字动画运动字幕GUI.exe
├─ 字字动画运动字幕修复.exe
├─ ffmpeg.exe
└─ ffprobe.exe
```

打包后的目标电脑不需要安装 Python、OpenCV 或 NumPy。目标电脑仍需要安装 Tesseract OCR，或者在 GUI 中选择 `tesseract.exe` 的路径；使用中文识别时还需要 Tesseract 的 `chi_sim` 语言包。

FFmpeg 建议与 EXE 放在同一文件夹，打包脚本会在项目目录找到 `ffmpeg.exe` 和 `ffprobe.exe` 时自动复制它们。
