#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量视频去字幕工具

依赖：Python 3.10+、FFmpeg、FFprobe。
默认处理每个视频底部 20% 区域，适合 Mini Max H3 常见固定字幕。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".flv"}


def find_binary(name: str, explicit: str | None = None) -> str | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
    local = Path(__file__).resolve().parent / (name + (".exe" if os.name == "nt" else ""))
    if local.exists():
        return str(local)
    return shutil.which(name) or shutil.which(name + ".exe")


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe_video(ffprobe: str, path: Path) -> tuple[int, int, float]:
    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration:format=duration",
        "-of", "json", str(path),
    ]
    result = run_capture(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "无法读取视频信息")
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration = float(stream.get("duration") or (data.get("format") or {}).get("duration") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("视频没有可读取的视频流")
    return width, height, duration


def parse_region(value: str) -> tuple[int, int, int, int]:
    try:
        numbers = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("区域格式必须是 x,y,w,h，例如 80,720,1120,180") from exc
    if len(numbers) != 4 or numbers[2] <= 0 or numbers[3] <= 0 or min(numbers[:2]) < 0:
        raise argparse.ArgumentTypeError("区域格式必须是非负 x,y 加正数 w,h")
    return numbers  # type: ignore[return-value]


def clamp_region(width: int, height: int, region: tuple[int, int, int, int] | None, left: float, top: float, region_width: float, region_height: float) -> tuple[int, int, int, int]:
    if region:
        x, y, w, h = region
    else:
        x = round(width * left)
        y = round(height * top)
        w = round(width * region_width)
        h = round(height * region_height)
    x = max(0, min(x, width - 2))
    y = max(0, min(y, height - 2))
    w = max(2, min(w, width - x))
    h = max(2, min(h, height - y))
    return x, y, w, h


def build_output_path(input_path: Path, input_root: Path, output_root: Path, suffix: str, recursive: bool) -> Path:
    relative_parent = input_path.parent.relative_to(input_root) if recursive else Path()
    return output_root / relative_parent / f"{input_path.stem}{suffix}{input_path.suffix}"


def collect_videos(input_root: Path, recursive: bool) -> list[Path]:
    iterator = input_root.rglob("*") if recursive else input_root.glob("*")
    return sorted(path for path in iterator if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def process_one_inpaint(args: argparse.Namespace, ffmpeg: str, input_path: Path, output_path: Path, x: int, y: int, w: int, h: int, index: int, total: int, duration: float) -> bool:
    """逐帧 OpenCV Inpainting，然后用 FFmpeg 合回原音频。"""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Inpainting 需要安装 opencv-python 和 numpy：python -m pip install opencv-python numpy") from exc

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV 无法打开视频")
    video_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if video_width <= 0 or video_height <= 0:
        capture.release()
        raise RuntimeError("无法读取视频分辨率")
    mask = np.zeros((video_height, video_width), dtype=np.uint8)
    mask[y:y + h, x:x + w] = 255
    flag = cv2.INPAINT_NS if args.method == "ns" else cv2.INPAINT_TELEA
    with tempfile.TemporaryDirectory(prefix="zizi_inpaint_") as temp:
        silent_path = Path(temp) / "silent.mp4"
        writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (video_width, video_height))
        if not writer.isOpened():
            capture.release()
            raise RuntimeError("OpenCV 无法创建临时视频，请检查视频编码器")
        print(f"[{index}/{total}] Inpainting {args.method.upper()}：{input_path.name}  区域={x},{y},{w},{h}")
        frame_no = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            repaired = cv2.inpaint(frame, mask, float(args.inpaint_radius), flag)
            writer.write(repaired)
            frame_no += 1
            if frame_no % max(1, int(fps)) == 0:
                percent = min(100.0, frame_no / frame_count * 100) if frame_count > 0 else 0
                print(f"    修复进度 {percent:5.1f}%", end="\r", flush=True)
        capture.release()
        writer.release()
        print(" " * 60, end="\r")
        if frame_no == 0 or not silent_path.exists():
            raise RuntimeError("没有生成有效的视频帧")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mux_command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y" if args.overwrite else "-n",
            "-i", str(silent_path), "-i", str(input_path),
            "-map", "0:v:0", "-map", "1:a?", "-c:v", "libx264",
            "-preset", args.preset, "-crf", "28" if args.fast else "20",
            "-c:a", "aac", "-b:a", args.audio_bitrate, "-shortest", "-movflags", "+faststart", str(output_path),
        ]
        result = run_capture(mux_command)
        if result.returncode != 0 or not output_path.exists():
            raise RuntimeError(result.stderr.strip() or "FFmpeg 合并音频失败")
    return True


def process_one(args: argparse.Namespace, ffmpeg: str, ffprobe: str, input_path: Path, output_path: Path, index: int, total: int) -> bool:
    started = time.time()
    try:
        width, height, duration = probe_video(ffprobe, input_path)
        x, y, w, h = clamp_region(width, height, args.region, args.left, args.top, args.region_width, args.region_height)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not args.overwrite:
            print(f"[{index}/{total}] 跳过（输出已存在）：{input_path.name}")
            return True

        if args.method in ("telea", "ns"):
            process_one_inpaint(args, ffmpeg, input_path, output_path, x, y, w, h, index, total, duration)
            elapsed = time.time() - started
            print(f"[{index}/{total}] 完成：{output_path.name}（Inpainting，耗时 {elapsed:.1f}s）")
            return True

        # delogo 根据字幕周边像素进行插值修复；map 语法允许没有音频的视频正常输出。
        filter_expr = f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"
        crf = "28" if args.fast else "20"
        command = [
            ffmpeg, "-hide_banner", "-nostats", "-y" if args.overwrite else "-n",
            "-i", str(input_path),
            "-map", "0:v:0", "-map", "0:a?",
            "-vf", filter_expr,
            "-c:v", "libx264", "-preset", args.preset, "-crf", crf,
            "-c:a", "aac", "-b:a", args.audio_bitrate,
            "-movflags", "+faststart", str(output_path),
        ]
        print(f"[{index}/{total}] 处理中：{input_path.name}  区域={x},{y},{w},{h}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        last_report = 0.0
        current = 0.0
        assert process.stdout is not None
        for line in process.stdout:
            if "time=" in line:
                try:
                    time_text = line.split("time=", 1)[1].split()[0]
                    hh, mm, ss = time_text.split(":")
                    current = int(hh) * 3600 + int(mm) * 60 + float(ss)
                    now = time.time()
                    if now - last_report >= 0.5:
                        percent = min(100.0, current / duration * 100) if duration > 0 else 0
                        print(f"    进度 {percent:5.1f}% ({format_time(current)}/{format_time(duration)})", end="\r", flush=True)
                        last_report = now
                except (ValueError, IndexError):
                    pass
        return_code = process.wait()
        print(" " * 80, end="\r")
        if return_code != 0 or not output_path.exists():
            print(f"[{index}/{total}] 失败：{input_path.name}")
            return False
        elapsed = time.time() - started
        print(f"[{index}/{total}] 完成：{output_path.name}（耗时 {elapsed:.1f}s）")
        return True
    except Exception as exc:
        print(f"[{index}/{total}] 失败：{input_path.name}：{exc}")
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量处理文件夹中的视频，去除固定区域字幕。")
    parser.add_argument("input", type=Path, help="输入视频文件夹")
    parser.add_argument("-o", "--output", type=Path, help="输出文件夹，默认在输入文件夹旁创建 output_removed")
    parser.add_argument("--recursive", action="store_true", help="递归扫描子文件夹，并在输出目录保留相同层级")
    parser.add_argument("--region", type=parse_region, help="固定像素区域 x,y,w,h，例如 80,720,1120,180")
    parser.add_argument("--left", type=float, default=0.04, help="默认区域左边界比例，默认 0.04")
    parser.add_argument("--top", type=float, default=0.76, help="默认区域上边界比例，默认 0.76")
    parser.add_argument("--region-width", type=float, default=0.92, dest="region_width", help="默认区域宽度比例，默认 0.92")
    parser.add_argument("--region-height", type=float, default=0.20, dest="region_height", help="默认区域高度比例，默认 0.20")
    parser.add_argument("--suffix", default="_去字幕", help="输出文件名后缀，默认 _去字幕")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的同名输出文件")
    parser.add_argument("--fast", action="store_true", help="快速模式，文件更小但画质略有损失")
    parser.add_argument("--method", choices=("delogo", "telea", "ns"), default="delogo", help="修复算法：delogo 快速；telea 细节较好；ns 更平滑")
    parser.add_argument("--inpaint-radius", type=float, default=3.0, dest="inpaint_radius", help="Inpainting 修复半径，默认 3.0，复杂背景可尝试 4-6")
    parser.add_argument("--preset", choices=("ultrafast", "veryfast", "fast", "medium"), default="veryfast", help="H.264 编码速度，默认 veryfast")
    parser.add_argument("--audio-bitrate", default="192k", help="输出音频码率，默认 192k")
    parser.add_argument("--ffmpeg", help="指定 ffmpeg 可执行文件路径")
    parser.add_argument("--ffprobe", help="指定 ffprobe 可执行文件路径")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_root = args.input.expanduser().resolve()
    if not input_root.is_dir():
        print(f"输入文件夹不存在：{input_root}", file=sys.stderr)
        return 2
    output_root = (args.output.expanduser().resolve() if args.output else input_root.parent / f"{input_root.name}_output")
    if output_root == input_root:
        print("输出文件夹不能与输入文件夹相同，请使用 -o 指定其他目录。", file=sys.stderr)
        return 2
    ffmpeg = find_binary("ffmpeg", args.ffmpeg)
    ffprobe = find_binary("ffprobe", args.ffprobe)
    if not ffmpeg or not ffprobe:
        print("找不到 ffmpeg 或 ffprobe。请安装 FFmpeg，加入 PATH，或用 --ffmpeg/--ffprobe 指定路径。", file=sys.stderr)
        return 2
    videos = collect_videos(input_root, args.recursive)
    if not videos:
        print("输入文件夹中没有找到支持的视频文件。")
        return 0

    print(f"找到 {len(videos)} 个视频")
    print(f"输出目录：{output_root}")
    print(f"字幕区域：{'固定 ' + ','.join(map(str, args.region)) if args.region else '按视频尺寸自动计算'}")
    print(f"修复算法：{args.method}")
    print()
    success = 0
    failed: list[Path] = []
    for index, input_path in enumerate(videos, 1):
        output_path = build_output_path(input_path, input_root, output_root, args.suffix, args.recursive)
        if process_one(args, ffmpeg, ffprobe, input_path, output_path, index, len(videos)):
            success += 1
        else:
            failed.append(input_path)

    print("\n批量处理完成")
    print(f"成功：{success}  失败：{len(failed)}  总数：{len(videos)}")
    if failed:
        print("失败文件：")
        for path in failed:
            print(f"  - {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
