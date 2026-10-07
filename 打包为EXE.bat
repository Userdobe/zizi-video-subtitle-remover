@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name 字字动画去字幕 subtitle_remover.py
 echo.
 echo 打包完成：dist\字字动画去字幕\字字动画去字幕.exe
 echo 请将 ffmpeg.exe 和 ffprobe.exe 放到 exe 同目录后再使用。
pause
