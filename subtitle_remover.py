#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字字动画 - 视频去字幕工具
纯标准库 GUI，依赖本机 ffmpeg/ffprobe。
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

VIDEO_TYPES = [("视频文件", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("所有文件", "*.*")]


def find_bin(name):
    exe = name + (".exe" if os.name == "nt" else "")
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), exe)
    if os.path.exists(local):
        return local
    return shutil.which(exe) or shutil.which(name)


FFMPEG = find_bin("ffmpeg")
FFPROBE = find_bin("ffprobe")


def run_capture(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")


def probe_video(path):
    if not FFPROBE:
        raise RuntimeError("找不到 ffprobe，请先安装 FFmpeg，或把 ffprobe.exe 放到软件同目录。")
    r = run_capture([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration,r_frame_rate", "-of", "json", path])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "无法读取视频信息")
    data = json.loads(r.stdout)
    stream = data.get("streams", [{}])[0]
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    duration = float(stream.get("duration") or 0)
    rate = stream.get("r_frame_rate", "")
    return width, height, duration, rate


class SubtitleRemover(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("字字动画 · 视频去字幕")
        self.geometry("1100x760")
        self.minsize(900, 650)
        self.configure(bg="#0f172a")
        self.video_path = ""
        self.preview_path = ""
        self.video_w = self.video_h = 0
        self.duration = 0
        self.scale = 1.0
        self.offset_x = self.offset_y = 0
        self.drag_start = None
        self.rect_id = None
        self.info_queue = queue.Queue()
        self.proc = None
        self._build_style()
        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8), background="#1e293b", foreground="#e2e8f0")
        style.map("TButton", background=[("active", "#334155")])
        style.configure("Accent.TButton", background="#38bdf8", foreground="#082f49", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#7dd3fc")])
        style.configure("TLabel", background="#0f172a", foreground="#cbd5e1", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#0f172a", foreground="#f8fafc", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#0f172a", foreground="#94a3b8", font=("Microsoft YaHei UI", 10))
        style.configure("TLabelframe", background="#0f172a", foreground="#cbd5e1")
        style.configure("TLabelframe.Label", background="#0f172a", foreground="#7dd3fc")
        style.configure("Horizontal.TProgressbar", troughcolor="#1e293b", background="#38bdf8", bordercolor="#1e293b", lightcolor="#38bdf8", darkcolor="#38bdf8")

    def _build_ui(self):
        top = tk.Frame(self, bg="#0f172a")
        top.pack(fill="x", padx=28, pady=(22, 6))
        ttk.Label(top, text="字字动画 · 视频去字幕", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="局部智能修复 · 保留原音频 · 本地处理不上传视频", style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

        main = tk.Frame(self, bg="#0f172a")
        main.pack(fill="both", expand=True, padx=28, pady=16)
        left = tk.Frame(main, bg="#111827", highlightthickness=1, highlightbackground="#1e293b")
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        right = tk.Frame(main, bg="#0f172a", width=330)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self.canvas = tk.Canvas(left, bg="#020617", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.placeholder = self.canvas.create_text(400, 260, text="选择视频后，在画面上拖动框选字幕区域", fill="#64748b", font=("Microsoft YaHei UI", 14))

        # control cards
        file_box = ttk.LabelFrame(right, text="1 选择视频", padding=12)
        file_box.pack(fill="x", pady=(0, 12))
        ttk.Button(file_box, text="打开视频", command=self.open_video).pack(fill="x")
        self.file_label = ttk.Label(file_box, text="尚未选择视频", style="Sub.TLabel", wraplength=285)
        self.file_label.pack(anchor="w", pady=(8, 0))
        self.meta_label = ttk.Label(file_box, text="", style="Sub.TLabel")
        self.meta_label.pack(anchor="w", pady=(4, 0))

        mode_box = ttk.LabelFrame(right, text="2 设置去字幕区域", padding=12)
        mode_box.pack(fill="x", pady=(0, 12))
        ttk.Button(mode_box, text="智能推荐底部字幕区", command=self.auto_region).pack(fill="x")
        ttk.Label(mode_box, text="也可以直接在左侧画面上拖动框选。", style="Sub.TLabel", wraplength=285).pack(anchor="w", pady=(8, 10))
        grid = tk.Frame(mode_box, bg="#0f172a")
        grid.pack(fill="x")
        self.vars = {k: tk.StringVar(value="0") for k in ("x", "y", "w", "h")}
        for i, key in enumerate(("x", "y", "w", "h")):
            ttk.Label(grid, text=key.upper()).grid(row=0, column=i, sticky="w", padx=(0, 5))
            ttk.Entry(grid, textvariable=self.vars[key], width=7).grid(row=1, column=i, padx=(0, 5), pady=(3, 0))
        ttk.Label(mode_box, text="坐标为原视频像素，建议框住字幕及少量上下边缘。", style="Sub.TLabel", wraplength=285).pack(anchor="w", pady=(9, 0))

        out_box = ttk.LabelFrame(right, text="3 输出设置", padding=12)
        out_box.pack(fill="x", pady=(0, 12))
        self.output_var = tk.StringVar()
        ttk.Entry(out_box, textvariable=self.output_var).pack(fill="x", side="left", expand=True)
        ttk.Button(out_box, text="浏览", command=self.choose_output).pack(side="right", padx=(8, 0))
        self.fast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(out_box, text="快速模式（画质略有损失）", variable=self.fast_var).pack(anchor="w", pady=(10, 0))

        self.export_btn = ttk.Button(right, text="开始去字幕并导出", style="Accent.TButton", command=self.start_export)
        self.export_btn.pack(fill="x", pady=(4, 10))
        self.progress = ttk.Progressbar(right, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="等待选择视频")
        ttk.Label(right, textvariable=self.status_var, style="Sub.TLabel", wraplength=300).pack(anchor="w", pady=(8, 0))

        tips = ttk.LabelFrame(right, text="使用说明", padding=12)
        tips.pack(fill="x", pady=(18, 0))
        ttk.Label(tips, text="• Mini Max H3 生成的固定字幕，推荐先点“智能推荐底部字幕区”。\n• 字幕位置复杂时，请手动画框。\n• 输出采用 H.264 MP4，并尽量复制原音频。\n• 画面复杂或字幕覆盖人物时，效果可能需要多次尝试。", style="Sub.TLabel", wraplength=285, justify="left").pack(anchor="w")

    def open_video(self):
        path = filedialog.askopenfilename(title="选择视频", filetypes=VIDEO_TYPES)
        if not path:
            return
        try:
            self.video_w, self.video_h, self.duration, rate = probe_video(path)
            self.video_path = path
            self.file_label.configure(text=os.path.basename(path), foreground="#e2e8f0")
            self.meta_label.configure(text=f"{self.video_w} × {self.video_h} · {self.duration:.1f} 秒")
            self.output_var.set(os.path.splitext(path)[0] + "_去字幕.mp4")
            self._make_preview()
            self.auto_region()
            self.status_var.set("已加载视频，请确认字幕区域后导出")
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def _make_preview(self):
        if not FFMPEG:
            raise RuntimeError("找不到 ffmpeg，请先安装 FFmpeg，或把 ffmpeg.exe 放到软件同目录。")
        self.preview_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".preview_frame.png")
        r = run_capture([FFMPEG, "-y", "-ss", "0", "-i", self.video_path, "-frames:v", "1", "-vf", "scale=960:-2", self.preview_path])
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-800:])
        self._redraw()

    def _redraw(self):
        if not self.preview_path or not os.path.exists(self.preview_path):
            return
        try:
            img = tk.PhotoImage(file=self.preview_path)
        except Exception:
            return
        cw, ch = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        iw, ih = img.width(), img.height()
        scale = min((cw - 24) / iw, (ch - 24) / ih, 1.0)
        if scale < 1:
            # PhotoImage only supports integer downsampling; preview is already capped at 960px.
            factor = max(1, int(round(1 / scale)))
            img = img.subsample(factor, factor)
            iw, ih = img.width(), img.height()
        self.tk_img = img
        self.offset_x, self.offset_y = (cw - iw) / 2, (ch - ih) / 2
        self.scale = iw / max(self.video_w, 1)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.tk_img, anchor="nw")
        self._draw_region()

    def _draw_region(self):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        try:
            x, y, w, h = [int(self.vars[k].get()) for k in ("x", "y", "w", "h")]
        except ValueError:
            return
        if w <= 0 or h <= 0 or not self.video_w:
            return
        x1 = self.offset_x + x * self.scale
        y1 = self.offset_y + y * self.scale
        x2 = x1 + w * self.scale
        y2 = y1 + h * self.scale
        self.rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#fbbf24", width=3, dash=(8, 4))
        self.canvas.create_text(x1 + 8, y1 + 8, text="字幕修复区", anchor="nw", fill="#fbbf24", font=("Microsoft YaHei UI", 10, "bold"))

    def auto_region(self):
        if not self.video_w:
            return
        # 默认覆盖底部 22%，但左右留少量边界，适合大多数 H3 字幕
        self.vars["x"].set(str(int(self.video_w * 0.04)))
        self.vars["y"].set(str(int(self.video_h * 0.76)))
        self.vars["w"].set(str(int(self.video_w * 0.92)))
        self.vars["h"].set(str(int(self.video_h * 0.20)))
        self._draw_region()

    def _canvas_to_video(self, x, y):
        return int(max(0, min(self.video_w, (x - self.offset_x) / max(self.scale, 0.001)))), int(max(0, min(self.video_h, (y - self.offset_y) / max(self.scale, 0.001))))

    def _drag_start(self, e):
        if not self.video_path:
            return
        self.drag_start = self._canvas_to_video(e.x, e.y)

    def _drag_move(self, e):
        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = self._canvas_to_video(e.x, e.y)
        x, y, w, h = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
        for k, value in zip(("x", "y", "w", "h"), (x, y, w, h)):
            self.vars[k].set(str(value))
        self._draw_region()

    def _drag_end(self, e):
        self._drag_move(e)
        self.drag_start = None

    def choose_output(self):
        path = filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".mp4", filetypes=[("MP4 视频", "*.mp4")])
        if path:
            self.output_var.set(path)

    def start_export(self):
        if not self.video_path:
            messagebox.showwarning("提示", "请先选择视频文件。")
            return
        try:
            x, y, w, h = [int(self.vars[k].get()) for k in ("x", "y", "w", "h")]
        except ValueError:
            messagebox.showwarning("提示", "字幕区域坐标必须是整数。")
            return
        if w < 2 or h < 2 or x + w > self.video_w or y + h > self.video_h:
            messagebox.showwarning("提示", "字幕区域超出视频范围，请重新框选。")
            return
        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning("提示", "请选择输出文件。")
            return
        if not FFMPEG:
            messagebox.showerror("缺少 FFmpeg", "请安装 FFmpeg，并把 ffmpeg.exe 加入 PATH 或放到软件同目录。")
            return
        self.export_btn.configure(state="disabled")
        self.progress.configure(value=0, maximum=max(self.duration, 1))
        self.status_var.set("处理中，请不要关闭窗口…")
        threading.Thread(target=self._export_worker, args=(x, y, w, h, output), daemon=True).start()

    def _export_worker(self, x, y, w, h, output):
        # delogo 会根据周围像素进行插值修复；保留原视频音频并用 faststart 便于播放。
        vf = f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"
        crf = "28" if self.fast_var.get() else "20"
        cmd = [FFMPEG, "-y", "-i", self.video_path, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", crf, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            last = ""
            while True:
                line = self.proc.stderr.readline()
                if not line and self.proc.poll() is not None:
                    break
                if line:
                    last = line.strip()
                    m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                    if m:
                        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        self.info_queue.put(("progress", min(seconds, self.duration)))
            code = self.proc.wait()
            if code == 0 and os.path.exists(output):
                self.info_queue.put(("done", output))
            else:
                self.info_queue.put(("error", last or "FFmpeg 处理失败"))
        except Exception as e:
            self.info_queue.put(("error", str(e)))

    def _poll_queue(self):
        try:
            while True:
                kind, value = self.info_queue.get_nowait()
                if kind == "progress":
                    self.progress.configure(value=value)
                    self.status_var.set(f"处理中… {value:.1f} / {self.duration:.1f} 秒")
                elif kind == "done":
                    self.export_btn.configure(state="normal")
                    self.progress.configure(value=self.duration)
                    self.status_var.set("处理完成")
                    messagebox.showinfo("导出完成", f"视频已保存到：\n{value}")
                elif kind == "error":
                    self.export_btn.configure(state="normal")
                    self.status_var.set("处理失败")
                    messagebox.showerror("处理失败", value)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


if __name__ == "__main__":
    app = SubtitleRemover()
    app.mainloop()
