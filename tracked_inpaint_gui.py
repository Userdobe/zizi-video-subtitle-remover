#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运动字幕去除 GUI：调用 tracked_inpaint_remove.py。"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))


class TrackingGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("字字动画 · 运动字幕自动修复")
        self.geometry("920x700")
        self.minsize(820, 620)
        self.configure(bg="#0f172a")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
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

    def _build(self):
        top = tk.Frame(self, bg="#0f172a")
        top.pack(fill="x", padx=26, pady=(22, 5))
        ttk.Label(top, text="字字动画 · 运动字幕自动修复", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="OCR 初始检测 · Lucas-Kanade 光流跟踪 · Telea Inpainting", style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=26, pady=16)
        left = tk.Frame(body, bg="#0f172a", width=380)
        left.pack(side="left", fill="y", padx=(0, 18))
        left.pack_propagate(False)
        right = tk.Frame(body, bg="#111827", highlightthickness=1, highlightbackground="#1e293b")
        right.pack(side="right", fill="both", expand=True)

        files = ttk.LabelFrame(left, text="1 选择视频", padding=12)
        files.pack(fill="x", pady=(0, 12))
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.tesseract_var = tk.StringVar()
        self._path_row(files, "输入视频", self.input_var, self.pick_input)
        self._path_row(files, "输出视频", self.output_var, self.pick_output)
        self._path_row(files, "Tesseract 路径（可选）", self.tesseract_var, self.pick_tesseract)
        ttk.Label(files, text="如果 tesseract.exe 已加入 PATH，可以留空。", style="Sub.TLabel", wraplength=340).pack(anchor="w")

        params = ttk.LabelFrame(left, text="2 跟踪参数", padding=12)
        params.pack(fill="x", pady=(0, 12))
        self.vars = {
            "language": tk.StringVar(value="chi_sim+eng"),
            "redetect": tk.StringVar(value="8"),
            "confidence": tk.StringVar(value="0.35"),
            "scene": tk.StringVar(value="35"),
            "radius": tk.StringVar(value="3"),
            "dilate": tk.StringVar(value="2"),
        }
        rows = [("OCR 语言", "language"), ("OCR 重检测间隔（帧）", "redetect"), ("光流置信度", "confidence"), ("场景切换阈值", "scene"), ("Inpainting 半径", "radius"), ("遮罩外扩像素", "dilate")]
        for label, key in rows:
            row = tk.Frame(params, bg="#0f172a")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label).pack(side="left")
            ttk.Entry(row, textvariable=self.vars[key], width=14).pack(side="right")
        ttk.Label(params, text="推荐：重检测 8，置信度 0.35，半径 3。", style="Sub.TLabel", wraplength=340).pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(left, bg="#0f172a")
        buttons.pack(fill="x", pady=(2, 0))
        self.start_btn = ttk.Button(buttons, text="开始处理", style="Accent.TButton", command=self.start)
        self.start_btn.pack(fill="x", pady=(0, 8))
        self.stop_btn = ttk.Button(buttons, text="停止处理", command=self.stop, state="disabled")
        self.stop_btn.pack(fill="x")
        self.status = tk.StringVar(value="请选择输入视频")
        ttk.Label(left, textvariable=self.status, style="Sub.TLabel", wraplength=360).pack(anchor="w", pady=(12, 0))

        ttk.Label(right, text="处理日志", style="Sub.TLabel").pack(anchor="w", padx=14, pady=(12, 7))
        self.log = tk.Text(right, bg="#020617", fg="#cbd5e1", insertbackground="#f8fafc", relief="flat", wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _path_row(self, parent, label, variable, command):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(2, 0))
        row = tk.Frame(parent, bg="#0f172a")
        row.pack(fill="x", pady=(4, 9))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="浏览", command=command).pack(side="right", padx=(8, 0))

    def _log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def pick_input(self):
        path = filedialog.askopenfilename(title="选择输入视频", filetypes=[("视频", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("所有文件", "*.*")])
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.with_name(p.stem + "_去字幕" + p.suffix)))

    def pick_output(self):
        path = filedialog.asksaveasfilename(title="选择输出视频", defaultextension=".mp4", filetypes=[("MP4 视频", "*.mp4"), ("所有文件", "*.*")])
        if path:
            self.output_var.set(path)

    def pick_tesseract(self):
        path = filedialog.askopenfilename(title="选择 tesseract.exe", filetypes=[("Tesseract", "tesseract.exe"), ("所有文件", "*.*")])
        if path:
            self.tesseract_var.set(path)

    def start(self):
        input_path = Path(self.input_var.get()).expanduser()
        output_path = Path(self.output_var.get()).expanduser()
        if not input_path.is_file():
            messagebox.showwarning("提示", "请选择有效的输入视频。")
            return
        if input_path == output_path:
            messagebox.showwarning("提示", "输出文件不能覆盖原视频。")
            return
        try:
            float(self.vars["confidence"].get())
            int(self.vars["redetect"].get())
            float(self.vars["scene"].get())
            float(self.vars["radius"].get())
            int(self.vars["dilate"].get())
        except ValueError:
            messagebox.showwarning("提示", "跟踪参数格式不正确，请检查数值。")
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.set("处理中…")
        self._log("开始处理：" + str(input_path))
        threading.Thread(target=self._worker, args=(str(input_path), str(output_path)), daemon=True).start()

    def _worker(self, input_path: str, output_path: str):
        if getattr(sys, "frozen", False):
            worker = APP_DIR / "字字动画运动字幕修复.exe"
            if not worker.exists():
                self.events.put(("error", f"找不到处理引擎：{worker}"))
                return
            command = [str(worker), input_path, output_path]
        else:
            script = RESOURCE_DIR / "tracked_inpaint_remove.py"
            command = [sys.executable, str(script), input_path, output_path]
        command.extend(["--language", self.vars["language"].get(), "--redetect-interval", self.vars["redetect"].get(), "--flow-confidence", self.vars["confidence"].get(), "--scene-threshold", self.vars["scene"].get(), "--inpaint-radius", self.vars["radius"].get(), "--mask-dilate", self.vars["dilate"].get()])
        if self.tesseract_var.get().strip():
            command.extend(["--tesseract", self.tesseract_var.get().strip()])
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.events.put(("log", line.rstrip()))
            code = self.process.wait()
            self.events.put(("done", code))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status.set("正在停止…")

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._log(str(value))
                elif kind == "error":
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.status.set("启动失败")
                    messagebox.showerror("启动失败", str(value))
                elif kind == "done":
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    if int(value) == 0:
                        self.status.set("处理完成")
                        messagebox.showinfo("完成", "运动字幕修复已完成。")
                    else:
                        self.status.set("处理失败")
                        messagebox.showerror("处理失败", "处理引擎返回错误，请查看日志。")
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    TrackingGUI().mainloop()
