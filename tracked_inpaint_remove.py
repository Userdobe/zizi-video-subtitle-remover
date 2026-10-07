#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运动字幕去除：OCR 初始检测 + Lucas-Kanade 光流跟踪 + Telea Inpainting。

依赖：opencv-python、numpy、FFmpeg、Tesseract OCR。
示例：
    python tracked_inpaint_remove.py input.mp4 output.mp4 --redetect-interval 8
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError as exc:
    print("缺少依赖，请先执行：python -m pip install opencv-python numpy", file=sys.stderr)
    raise SystemExit(2) from exc


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def find_binary(name: str, explicit: str | None = None) -> str | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
    filename = name + (".exe" if os.name == "nt" else "")
    folders = [Path(sys.executable).resolve().parent] if getattr(sys, "frozen", False) else [Path(__file__).resolve().parent]
    folders.append(Path(__file__).resolve().parent)
    for folder in folders:
        local = folder / filename
        if local.exists():
            return str(local)
    return shutil.which(name) or shutil.which(name + ".exe")


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")


def probe_duration(ffprobe: str, path: Path) -> float:
    result = run_capture([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    if result.returncode != 0:
        return 0.0
    try:
        return float(json.loads(result.stdout).get("format", {}).get("duration") or 0)
    except (ValueError, json.JSONDecodeError):
        return 0.0


def clamp_box(box: tuple[int, int, int, int] | None, width: int, height: int) -> tuple[int, int, int, int] | None:
    if not box:
        return None
    x, y, w, h = box
    x = max(0, min(int(x), width - 2))
    y = max(0, min(int(y), height - 2))
    w = max(2, min(int(w), width - x))
    h = max(2, min(int(h), height - y))
    return x, y, w, h


def detect_subtitle_with_ocr(frame: np.ndarray, tesseract: str, temp_dir: Path, language: str, search_top: float, min_confidence: float) -> tuple[tuple[int, int, int, int] | None, int]:
    """使用 Tesseract TSV 结果提取画面下半部分文字，并合并成字幕框。"""
    height, width = frame.shape[:2]
    frame_path = temp_dir / "ocr_frame.png"
    cv2.imwrite(str(frame_path), frame)
    command = [tesseract, str(frame_path), "stdout", "--psm", "6", "-l", language, "tsv"]
    result = run_capture(command)
    if result.returncode != 0:
        return None, 0

    boxes: list[tuple[int, int, int, int]] = []
    reader = csv.DictReader(result.stdout.splitlines(), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        try:
            conf = float(row.get("conf") or -1)
            x = int(row.get("left") or 0)
            y = int(row.get("top") or 0)
            w = int(row.get("width") or 0)
            h = int(row.get("height") or 0)
        except ValueError:
            continue
        if text and conf >= min_confidence and y >= int(height * search_top) and w >= 3 and h >= 3:
            boxes.append((x, y, w, h))
    if not boxes:
        return None, 0

    pad_x = max(4, round(width * 0.012))
    pad_y = max(4, round(height * 0.018))
    left = max(0, min(x for x, _, _, _ in boxes) - pad_x)
    top = max(0, min(y for _, y, _, _ in boxes) - pad_y)
    right = min(width, max(x + w for x, _, w, _ in boxes) + pad_x)
    bottom = min(height, max(y + h for _, y, _, h in boxes) + pad_y)

    # OCR 只识别到一两个字时，横向扩展到一个合理的字幕宽度。
    if right - left < width * 0.28:
        center = (left + right) // 2
        half = round(width * 0.22)
        left, right = max(0, center - half), min(width, center + half)
    if bottom - top < height * 0.06:
        bottom = min(height, top + round(height * 0.10))
    return clamp_box((left, top, right - left, bottom - top), width, height), len(boxes)


def track_bbox_lucas_kanade(previous_gray: np.ndarray, current_gray: np.ndarray, bbox: tuple[int, int, int, int], args) -> tuple[tuple[int, int, int, int] | None, float]:
    """用稀疏 Lucas-Kanade 光流估计字幕框的平移与尺度变化。"""
    x, y, w, h = bbox
    height, width = previous_gray.shape[:2]
    margin = max(4, int(args.flow_margin))
    x0, y0 = max(0, x - margin), max(0, y - margin)
    x1, y1 = min(width, x + w + margin), min(height, y + h + margin)
    roi = previous_gray[y0:y1, x0:x1]
    if roi.size == 0:
        return None, 0.0
    points = cv2.goodFeaturesToTrack(roi, maxCorners=args.max_corners, qualityLevel=0.01, minDistance=4, blockSize=7)
    if points is None or len(points) < 4:
        return None, 0.0
    points[:, :, 0] += x0
    points[:, :, 1] += y0
    next_points, status, errors = cv2.calcOpticalFlowPyrLK(
        previous_gray, current_gray, points, None,
        winSize=(args.flow_window, args.flow_window),
        maxLevel=args.flow_levels,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if next_points is None or status is None:
        return None, 0.0
    good_old = points[status.ravel() == 1]
    good_new = next_points[status.ravel() == 1]
    if len(good_new) < 4:
        return None, len(good_new) / max(len(points), 1)
    deltas = good_new - good_old
    dx, dy = np.median(deltas, axis=0).ravel()
    # 光流质量：通过点比例和位移误差共同估计。
    median_error = float(np.median(errors[status.ravel() == 1])) if errors is not None else 0.0
    point_ratio = len(good_new) / max(len(points), 1)
    confidence = float(point_ratio * max(0.0, 1.0 - min(median_error / 30.0, 1.0)))
    if confidence < args.flow_confidence:
        return None, confidence
    # 限制单帧位移，避免场景切换造成字幕框跳到画面外。
    max_jump = max(20.0, min(width, height) * 0.15)
    dx, dy = float(np.clip(dx, -max_jump, max_jump)), float(np.clip(dy, -max_jump, max_jump))
    return clamp_box((round(x + dx), round(y + dy), w, h), width, height), confidence


def scene_change(previous_gray: np.ndarray | None, current_gray: np.ndarray, threshold: float) -> bool:
    if previous_gray is None:
        return False
    small_a = cv2.resize(previous_gray, (64, 36))
    small_b = cv2.resize(current_gray, (64, 36))
    return float(cv2.absdiff(small_a, small_b).mean()) >= threshold


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCR + Lucas-Kanade 光流 + Telea Inpainting 去除运动字幕")
    parser.add_argument("input", type=Path, help="输入视频")
    parser.add_argument("output", type=Path, help="输出视频")
    parser.add_argument("--tesseract", help="指定 tesseract.exe 路径")
    parser.add_argument("--language", default="chi_sim+eng", help="Tesseract 语言，默认 chi_sim+eng")
    parser.add_argument("--redetect-interval", type=int, default=8, help="每隔多少帧重新 OCR，默认 8")
    parser.add_argument("--search-top", type=float, default=0.50, help="OCR 只搜索画面该比例以下区域，默认 0.50")
    parser.add_argument("--ocr-confidence", type=float, default=25.0, help="OCR 最低置信度，默认 25")
    parser.add_argument("--flow-window", type=int, default=21, help="Lucas-Kanade 窗口大小，默认 21")
    parser.add_argument("--flow-levels", type=int, default=3, help="光流金字塔层数，默认 3")
    parser.add_argument("--flow-margin", type=int, default=12, help="字幕框周围光流搜索边缘，默认 12 像素")
    parser.add_argument("--max-corners", type=int, default=80, help="最多跟踪角点数，默认 80")
    parser.add_argument("--flow-confidence", type=float, default=0.35, help="光流低于此置信度时重新 OCR，默认 0.35")
    parser.add_argument("--scene-threshold", type=float, default=35.0, help="场景切换检测阈值，默认 35")
    parser.add_argument("--inpaint-radius", type=float, default=3.0, help="Telea 修复半径，默认 3")
    parser.add_argument("--mask-dilate", type=int, default=2, help="字幕遮罩膨胀像素，默认 2")
    parser.add_argument("--crf", type=int, default=20, help="输出视频质量，数值越小质量越高，默认 20")
    parser.add_argument("--preset", default="veryfast", choices=("ultrafast", "veryfast", "fast", "medium"), help="H.264 编码速度")
    parser.add_argument("--ffmpeg", help="指定 ffmpeg 路径")
    parser.add_argument("--ffprobe", help="指定 ffprobe 路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not input_path.is_file() or input_path.suffix.lower() not in VIDEO_EXTENSIONS:
        print(f"输入视频不存在或格式不支持：{input_path}", file=sys.stderr)
        return 2
    if output_path == input_path:
        print("输出文件不能覆盖原视频，请指定另一个路径。", file=sys.stderr)
        return 2
    ffmpeg = find_binary("ffmpeg", args.ffmpeg)
    ffprobe = find_binary("ffprobe", args.ffprobe)
    tesseract = find_binary("tesseract", args.tesseract)
    if not ffmpeg or not ffprobe:
        print("找不到 FFmpeg/FFprobe，请安装并加入 PATH。", file=sys.stderr)
        return 2
    if not tesseract:
        print("找不到 Tesseract OCR，请安装并加入 PATH，或使用 --tesseract 指定路径。", file=sys.stderr)
        return 2
    if args.redetect_interval < 1 or args.flow_window < 5 or args.flow_window % 2 == 0:
        print("redetect-interval 必须 >=1，flow-window 必须是 >=5 的奇数。", file=sys.stderr)
        return 2

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        print("OpenCV 无法打开输入视频。", file=sys.stderr)
        return 2
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = probe_duration(ffprobe, input_path)
    if width <= 0 or height <= 0:
        print("无法读取视频分辨率。", file=sys.stderr)
        capture.release()
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    previous_gray: np.ndarray | None = None
    bbox: tuple[int, int, int, int] | None = None
    frame_no = 0
    redetect_count = 0
    tracked_count = 0
    with tempfile.TemporaryDirectory(prefix="zizi_track_") as temp:
        temp_dir = Path(temp)
        silent_path = temp_dir / "silent.mp4"
        writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            capture.release()
            print("无法创建临时视频，请检查 OpenCV 编码器。", file=sys.stderr)
            return 2
        print(f"输入：{input_path}")
        print(f"分辨率：{width}x{height}，FPS：{fps:.2f}，时长：{duration:.1f}s")
        print("开始：OCR 定位 + Lucas-Kanade 跟踪 + Telea 修复")
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            force_redetect = (bbox is None and frame_no % args.redetect_interval == 0) or frame_no % args.redetect_interval == 0 or scene_change(previous_gray, gray, args.scene_threshold)
            current_bbox = None
            if force_redetect:
                current_bbox, detected = detect_subtitle_with_ocr(frame, tesseract, temp_dir, args.language, args.search_top, args.ocr_confidence)
                redetect_count += 1
                if current_bbox:
                    bbox = current_bbox
                    print(f"\n帧 {frame_no}: OCR 字幕框={bbox}，文字区域={detected}")
                else:
                    bbox = None
                    print(f"\n帧 {frame_no}: OCR 未发现字幕，当前帧不修复")
            elif previous_gray is not None and bbox is not None:
                tracked_bbox, confidence = track_bbox_lucas_kanade(previous_gray, gray, bbox, args)
                if tracked_bbox is not None:
                    bbox = tracked_bbox
                    tracked_count += 1
                else:
                    bbox = None
                    print(f"\n帧 {frame_no}: 光流跟踪失败，将在下一帧重新 OCR")

            if bbox is not None:
                x, y, w, h = bbox
                mask = np.zeros((height, width), dtype=np.uint8)
                mask[y:y + h, x:x + w] = 255
                if args.mask_dilate > 0:
                    kernel_size = args.mask_dilate * 2 + 1
                    mask = cv2.dilate(mask, np.ones((kernel_size, kernel_size), np.uint8), iterations=1)
                repaired = cv2.inpaint(frame, mask, args.inpaint_radius, cv2.INPAINT_TELEA)
                writer.write(repaired)
            else:
                writer.write(frame)
            previous_gray = gray
            frame_no += 1
            if frame_no % max(1, int(fps)) == 0:
                percent = min(100.0, frame_no / frame_count * 100) if frame_count > 0 else 0
                print(f"处理进度：{percent:5.1f}%  OCR={redetect_count}  光流={tracked_count}", end="\r", flush=True)
        capture.release()
        writer.release()
        print()
        if frame_no == 0:
            print("没有读取到视频帧。", file=sys.stderr)
            return 1

        mux_command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(silent_path), "-i", str(input_path),
            "-map", "0:v:0", "-map", "1:a?", "-c:v", "libx264", "-preset", args.preset,
            "-crf", str(args.crf), "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(output_path),
        ]
        mux = run_capture(mux_command)
        if mux.returncode != 0 or not output_path.exists():
            print(mux.stderr.strip() or "合并原音频失败。", file=sys.stderr)
            return 1
    print(f"完成：{output_path}")
    print(f"总帧数：{frame_no}，OCR 重定位：{redetect_count} 次，光流跟踪：{tracked_count} 帧，耗时：{time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
