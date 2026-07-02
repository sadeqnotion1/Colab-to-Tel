@echo off
rem Thin launcher - leecher + controller bots (one process).
chcp 65001 >nul
cd /d "%~dp0"
python -m colab_leecher.run_with_controller
pause
