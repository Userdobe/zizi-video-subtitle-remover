@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo 用法：批量去字幕.bat 输入视频文件夹 [输出文件夹]
  echo 示例：批量去字幕.bat D:\videos D:\videos_output
  pause
  exit /b 1
)
if "%~2"=="" (
  python batch_remove_subtitles.py "%~1" --recursive
) else (
  python batch_remove_subtitles.py "%~1" --recursive -o "%~2"
)
pause
