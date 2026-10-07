@echo off
chcp 65001 >nul
cd /d "%~dp0"
python batch_remove_gui.py
if errorlevel 1 pause
