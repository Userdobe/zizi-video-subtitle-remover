@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
if not exist requirements_inpainting.txt echo opencv-python>requirements_inpainting.txt
python -m PyInstaller --noconfirm --clean --onedir --console --name 字字动画批量去字幕 batch_remove_subtitles.py
python -m PyInstaller --noconfirm --clean --onedir --windowed --name 字字动画批量去字幕GUI batch_remove_gui.py
if exist ffmpeg.exe copy /Y ffmpeg.exe "dist\字字动画批量去字幕GUI\ffmpeg.exe"
if exist ffprobe.exe copy /Y ffprobe.exe "dist\字字动画批量去字幕GUI\ffprobe.exe"
if exist ffmpeg.exe copy /Y ffmpeg.exe "dist\字字动画批量去字幕\ffmpeg.exe"
if exist ffprobe.exe copy /Y ffprobe.exe "dist\字字动画批量去字幕\ffprobe.exe"
copy /Y "dist\字字动画批量去字幕\字字动画批量去字幕.exe" "dist\字字动画批量去字幕GUI\字字动画批量去字幕.exe"
if exist requirements_inpainting.txt copy /Y requirements_inpainting.txt "dist\字字动画批量去字幕GUI\requirements_inpainting.txt"
echo.
echo 打包完成：
echo   dist\字字动画批量去字幕GUI\字字动画批量去字幕GUI.exe
echo   dist\字字动画批量去字幕GUI\字字动画批量去字幕.exe
 echo 如果电脑没有安装 FFmpeg，请确认 ffmpeg.exe 与 ffprobe.exe 已复制到 GUI 文件夹。
echo Inpainting 模式需要在目标电脑安装：python -m pip install opencv-python numpy
pause
