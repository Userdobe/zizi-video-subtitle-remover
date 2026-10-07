@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --console --name 字字动画运动字幕修复 tracked_inpaint_remove.py
python -m PyInstaller --noconfirm --clean --onedir --windowed --name 字字动画运动字幕GUI tracked_inpaint_gui.py
if exist ffmpeg.exe copy /Y ffmpeg.exe "dist\字字动画运动字幕GUI\ffmpeg.exe"
if exist ffprobe.exe copy /Y ffprobe.exe "dist\字字动画运动字幕GUI\ffprobe.exe"
if exist ffmpeg.exe copy /Y ffmpeg.exe "dist\字字动画运动字幕修复\ffmpeg.exe"
if exist ffprobe.exe copy /Y ffprobe.exe "dist\字字动画运动字幕修复\ffprobe.exe"
copy /Y "dist\字字动画运动字幕修复\字字动画运动字幕修复.exe" "dist\字字动画运动字幕GUI\字字动画运动字幕修复.exe"
if exist requirements_tracking.txt copy /Y requirements_tracking.txt "dist\字字动画运动字幕GUI\requirements_tracking.txt"
echo.
echo 打包完成：
echo   dist\字字动画运动字幕GUI\字字动画运动字幕GUI.exe
echo   dist\字字动画运动字幕GUI\字字动画运动字幕修复.exe
echo.
echo 目标电脑还需要安装 Tesseract OCR，并确保 tesseract.exe 在 PATH 中，或在 GUI 中选择其路径。
echo 如果使用中文 OCR，请安装 chi_sim 中文语言包。
pause
