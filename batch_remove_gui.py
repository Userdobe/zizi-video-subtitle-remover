#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字字动画 - 批量去字幕 GUI
依赖：Python 标准库、FFmpeg/FFprobe；可选 Tesseract OCR。
"""
from __future__ import annotations

import csv
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".flv"}
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))


def find_binary(name: str) -> str | None:
    filename = name + (".exe" if os.name == "nt" else "")
    for folder in (BASE_DIR, RESOURCE_DIR):
        local = folder / filename
        if local.exists():
            return str(local)
    return shutil.which(name) or shutil.which(name + ".exe")


def capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe_video(path: Path) -> tuple[int, int, float]:
    ffprobe = find_binary("ffprobe")
    if not ffprobe:
        raise RuntimeError("找不到 ffprobe，请安装 FFmpeg，或把 ffprobe.exe 放到程序同目录。")
    result = capture([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration:format=duration", "-of", "json", str(path)])
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


def fallback_region(width: int, height: int) -> tuple[int, int, int, int]:
    return round(width * 0.04), round(height * 0.76), round(width * 0.92), round(height * 0.20)


def ocr_region(video: Path, message) -> tuple[tuple[int, int, int, int], str]:
    """从视频的三个采样帧中找字幕文字。失败时返回底部默认区域。"""
    ffmpeg = find_binary("ffmpeg")
    tesseract = find_binary("tesseract")
    width, height, duration = probe_video(video)
    default = fallback_region(width, height)
    if not tesseract:
        return default, "未检测到 Tesseract OCR，已使用底部字幕区域作为智能默认值。"
    if not ffmpeg:
        return default, "未检测到 FFmpeg，已使用底部字幕区域。"

    boxes: list[tuple[int, int, int, int]] = []
    with tempfile.TemporaryDirectory(prefix="zizi_ocr_") as temp:
        for index, ratio in enumerate((0.20, 0.50, 0.80), 1):
            frame = Path(temp) / f"frame_{index}.png"
            position = max(0.0, duration * ratio - 0.1) if duration else 0
            extract = capture([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{position:.2f}", "-i", str(video), "-frames:v", "1", str(frame)])
            if extract.returncode != 0 or not frame.exists():
                continue
            message(f"OCR 正在识别第 {index}/3 个采样画面…")
            result = capture([tesseract, str(frame), "stdout", "--psm", "6", "tsv"])
            if result.returncode != 0:
                continue
            reader = csv.DictReader(result.stdout.splitlines(), delimiter="\t")
            for row in reader:
                text = (row.get("text") or "").strip()
                try:
                    conf = float(row.get("conf") or -1)
                    x, y = int(row.get("left") or 0), int(row.get("top") or 0)
                    w, h = int(row.get("width") or 0), int(row.get("height") or 0)
                except ValueError:
                    continue
                # 只采纳画面下半部分的文字，减少把画面中的招牌误判为字幕。
                if text and conf >= 25 and y > height * 0.50 and w > 2 and h > 2:
                    boxes.append((x, y, w, h))

    if not boxes:
        return default, "OCR 未识别到稳定字幕，已使用底部字幕区域作为默认值。"
    left = max(0, min(item[0] for item in boxes) - round(width * 0.03))
    top = max(0, min(item[1] for item in boxes) - round(height * 0.05))
    right = min(width, max(item[0] + item[2] for item in boxes) + round(width * 0.03))
    bottom = min(height, max(item[1] + item[3] for item in boxes) + round(height * 0.08))
    # 字幕通常横向居中，OCR 只识别到部分字时扩大到合理宽度。
    if right - left < width * 0.40:
        center = (left + right) // 2
        half = round(width * 0.30)
        left, right = max(0, center - half), min(width, center + half)
    if bottom - top < height * 0.10:
        bottom = min(height, top + round(height * 0.14))
    return (left, top, right - left, bottom - top), f"OCR 已识别 {len(boxes)} 个文字区域。"


class BatchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("字字动画 · 批量视频去字幕")
        self.geometry("900x680")
        self.minsize(820, 600)
        self.configure(bg="#0f172a")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self._styles()
        self._build()
        self.after(100, self._poll)

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(10, 7))
        style.configure("Accent.TButton", background="#38bdf8", foreground="#082f49", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabel", background="#0f172a", foreground="#cbd5e1", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#0f172a", foreground="#f8fafc", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#0f172a", foreground="#94a3b8")
        style.configure("TLabelframe", background="#0f172a", foreground="#cbd5e1")
        style.configure("TLabelframe.Label", background="#0f172a", foreground="#7dd3fc")
        style.configure("Horizontal.TProgressbar", troughcolor="#1e293b", background="#38bdf8")

    def _build(self):
        top = tk.Frame(self, bg="#0f172a")
        top.pack(fill="x", padx=26, pady=(22, 4))
        ttk.Label(top, text="字字动画 · 批量视频去字幕", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="鼠标选择文件夹 · OCR 自动找字幕 · FFmpeg 本地批处理", style="Sub.TLabel").pack(anchor="w", pady=(5, 0))

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=26, pady=16)
        settings = tk.Frame(body, bg="#0f172a", width=390)
        settings.pack(side="left", fill="y", padx=(0, 18))
        settings.pack_propagate(False)
        log_frame = tk.Frame(body, bg="#111827", highlightthickness=1, highlightbackground="#1e293b")
        log_frame.pack(side="right", fill="both", expand=True)

        paths = ttk.LabelFrame(settings, text="1 选择文件夹", padding=12)
        paths.pack(fill="x", pady=(0, 12))
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self._path_row(paths, "输入文件夹", self.input_var, self.pick_input)
        self._path_row(paths, "输出文件夹", self.output_var, self.pick_output)
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(paths, text="包含子文件夹", variable=self.recursive_var).pack(anchor="w", pady=(7, 0))

        region = ttk.LabelFrame(settings, text="2 字幕区域", padding=12)
        region.pack(fill="x", pady=(0, 12))
        self.region_mode = tk.StringVar(value="ocr")
        ttk.Radiobutton(region, text="OCR 自动检测（推荐）", variable=self.region_mode, value="ocr").pack(anchor="w")
        ttk.Radiobutton(region, text="自动使用底部字幕区域", variable=self.region_mode, value="bottom").pack(anchor="w", pady=(6, 0))
        ttk.Radiobutton(region, text="手动像素区域", variable=self.region_mode, value="manual").pack(anchor="w", pady=(6, 0))
        self.region_var = tk.StringVar(value="80,720,1120,180")
        row = tk.Frame(region, bg="#0f172a")
        row.pack(fill="x", pady=(8, 0))
        ttk.Entry(row, textvariable=self.region_var).pack(side="left", fill="x", expand=True)
        ttk.Label(region, text="格式：x,y,w,h；OCR 不可用时会自动回退。", style="Sub.TLabel", wraplength=340).pack(anchor="w", pady=(7, 0))

        options = ttk.LabelFrame(settings, text="3 处理选项", padding=12)
        options.pack(fill="x", pady=(0, 12))
        self.overwrite_var = tk.BooleanVar(value=False)
        self.fast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="覆盖同名输出文件", variable=self.overwrite_var).pack(anchor="w")
        ttk.Checkbutton(options, text="快速模式（画质略有损失）", variable=self.fast_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(options, text="修复算法").pack(anchor="w", pady=(9, 0))
        self.method_var = tk.StringVar(value="delogo")
        ttk.Combobox(options, textvariable=self.method_var, state="readonly", values=("delogo", "telea", "ns")).pack(fill="x", pady=(4, 0))
        ttk.Label(options, text="delogo：最快；telea：细节较自然；ns：更平滑但较慢。", style="Sub.TLabel", wraplength=340).pack(anchor="w", pady=(5, 0))
        self.detect_btn = ttk.Button(settings, text="先检测字幕区域", command=self.detect)
        self.detect_btn.pack(fill="x", pady=(2, 8))
        self.start_btn = ttk.Button(settings, text="开始批量处理", style="Accent.TButton", command=self.start)
        self.start_btn.pack(fill="x", pady=(0, 8))
        self.stop_btn = ttk.Button(settings, text="停止当前处理", command=self.stop, state="disabled")
        self.stop_btn.pack(fill="x")
        self.progress = ttk.Progressbar(settings, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(16, 0))
        self.status = tk.StringVar(value="请选择输入文件夹")
        ttk.Label(settings, textvariable=self.status, style="Sub.TLabel", wraplength=370).pack(anchor="w", pady=(7, 0))

        ttk.Label(log_frame, text="处理日志", style="Sub.TLabel").pack(anchor="w", padx=14, pady=(12, 7))
        self.log = tk.Text(log_frame, bg="#020617", fg="#cbd5e1", insertbackground="#f8fafc", relief="flat", wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _path_row(self, parent, label, variable, command):
        ttk.Label(parent, text=label).pack(anchor="w")
        row = tk.Frame(parent, bg="#0f172a")
        row.pack(fill="x", pady=(4, 10))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="浏览", command=command).pack(side="right", padx=(8, 0))

    def _log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def pick_input(self):
        path = filedialog.askdirectory(title="选择输入视频文件夹")
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).parent / f"{Path(path).name}_output"))

    def pick_output(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_var.set(path)

    def first_video(self) -> Path | None:
        root = Path(self.input_var.get()).expanduser()
        if not root.is_dir():
            return None
        iterator = root.rglob("*") if self.recursive_var.get() else root.glob("*")
        videos = sorted(p for p in iterator if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
        return videos[0] if videos else None

    def detect(self):
        video = self.first_video()
        if not video:
            messagebox.showwarning("提示", "请先选择包含视频的输入文件夹。")
            return
        self.detect_btn.configure(state="disabled")
        self.status.set("正在检测字幕区域…")
        self._log(f"开始检测：{video.name}")
        threading.Thread(target=self._detect_worker, args=(video,), daemon=True).start()

    def _detect_worker(self, video: Path):
        try:
            region, info = ocr_region(video, lambda text: self.events.put(("log", text)))
            self.events.put(("region", region))
            self.events.put(("log", info))
            self.events.put(("status", f"检测区域：{','.join(map(str, region))}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.events.put(("detect_done", None))

    def start(self):
        input_dir = Path(self.input_var.get()).expanduser()
        if not input_dir.is_dir():
            messagebox.showwarning("提示", "请选择有效的输入文件夹。")
            return
        output_dir = Path(self.output_var.get()).expanduser() if self.output_var.get().strip() else input_dir.parent / f"{input_dir.name}_output"
        self.output_var.set(str(output_dir))
        self.start_btn.configure(state="disabled")
        self.detect_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_event.clear()
        self.progress.configure(value=0, maximum=1)
        self.status.set("正在准备批量处理…")
        self._log("开始批量处理")
        config = {
            "input": str(input_dir),
            "output": str(output_dir),
            "recursive": self.recursive_var.get(),
            "region_mode": self.region_mode.get(),
            "region": self.region_var.get().strip(),
            "overwrite": self.overwrite_var.get(),
            "fast": self.fast_var.get(),
            "method": self.method_var.get(),
        }
        self.worker = threading.Thread(target=self._run_batch, args=(config,), daemon=True)
        self.worker.start()

    def _run_batch(self, config):
        script = RESOURCE_DIR / "batch_remove_subtitles.py"
        if getattr(sys, "frozen", False):
            runner = BASE_DIR / "字字动画批量去字幕.exe"
            if not runner.exists():
                self.events.put(("error", f"找不到批处理引擎：{runner}，请重新运行打包脚本。"))
                return
            command_prefix = [str(runner)]
        else:
            if not script.exists():
                self.events.put(("error", f"找不到批量脚本：{script}"))
                return
            command_prefix = [sys.executable, str(script)]
        if config["region_mode"] == "manual":
            region = config["region"]
            try:
                values = [int(v.strip()) for v in region.split(",")]
                if len(values) != 4:
                    raise ValueError
            except ValueError:
                self.events.put(("error", "手动区域格式错误，应为 x,y,w,h"))
                return
        elif config["region_mode"] == "ocr":
            input_root = Path(config["input"])
            candidates = input_root.rglob("*") if config["recursive"] else input_root.glob("*")
            videos = sorted(p for p in candidates if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
            video = videos[0] if videos else None
            try:
                region_tuple, info = ocr_region(video, lambda text: self.events.put(("log", text))) if video else (None, "")
                if region_tuple:
                    region = ",".join(map(str, region_tuple))
                    self.events.put(("region", region_tuple))
                else:
                    region = ""
                self.events.put(("log", info))
            except Exception as exc:
                self.events.put(("log", f"OCR 检测失败，回退到自动底部区域：{exc}"))
                region = ""
        else:
            region = ""

        command = command_prefix + [config["input"], "-o", config["output"]]
        if config["recursive"]:
            command.append("--recursive")
        if region:
            command.extend(["--region", region])
        if config["overwrite"]:
            command.append("--overwrite")
        if config["fast"]:
            command.append("--fast")
        if config["method"] != "delogo":
            command.extend(["--method", config["method"]])
        self.events.put(("log", "执行：" + " ".join(f'"{x}"' if " " in x else x for x in command)))
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
            assert process.stdout is not None
            for line in process.stdout:
                if self.stop_event.is_set():
                    process.terminate()
                    self.events.put(("log", "已请求停止当前任务。"))
                    self.events.put(("done", -1))
                    return
                self.events.put(("log", line.rstrip()))
            code = process.wait()
            self.events.put(("done", code))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def stop(self):
        self.stop_event.set()
        self.status.set("正在停止，请稍候…")

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._log(str(value))
                elif kind == "region":
                    self.region_var.set(",".join(map(str, value)))
                elif kind == "status":
                    self.status.set(str(value))
                elif kind == "error":
                    self._log("错误：" + str(value))
                    self.status.set("操作失败")
                    self.start_btn.configure(state="normal")
                    self.detect_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    messagebox.showerror("操作失败", str(value))
                elif kind == "detect_done":
                    self.detect_btn.configure(state="normal")
                elif kind == "done":
                    code = int(value)
                    self.start_btn.configure(state="normal")
                    self.detect_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.status.set("批量处理完成" if code == 0 else "批量处理完成，但有文件失败")
                    if code == 0:
                        messagebox.showinfo("完成", "批量去字幕已完成。")
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    BatchGUI().mainloop()
