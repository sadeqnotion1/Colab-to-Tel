@echo off
echo ================================================
echo   Stopping Colab Telegram Leecher Bot
echo ================================================
echo.

REM Kill Python processes running colab_leecher
echo Searching for bot processes...
taskkill /F /FI "WINDOWTITLE eq *colab_leecher*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *colab_leecher*" 2>nul

REM Alternative: Kill all Python processes (use with caution)
REM taskkill /F /IM python.exe 2>nul

echo.
echo Checking for remaining processes...
tasklist | findstr /I "python.exe" >nul
if %errorlevel% equ 0 (
    echo.
    echo Warning: Some Python processes are still running:
    tasklist | findstr /I "python.exe"
    echo.
    echo If the bot is still running, you may need to close it manually
    echo or use Ctrl+C in the terminal window where it's running.
) else (
    echo No Python processes found. Bot should be stopped.
)

echo.
echo ================================================
echo   Done!
echo ================================================
pause
