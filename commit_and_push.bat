@echo off
echo ====================================================
echo   Git Auto-Commit and Push - Telegram Leecher Bot
echo ====================================================
echo Setting SOCKS5 proxy (socks5://127.0.0.1:1080)...
git config http.proxy socks5://127.0.0.1:1080
git config https.proxy socks5://127.0.0.1:1080
echo.
echo Adding changes...
git add -A
echo.
set commit_msg=Auto-update: Default Telegram upload to split .7z archives
echo Committing changes...
git commit -m "%commit_msg%"
echo.
echo Pushing to remote repository...
git push
echo.
echo Git commit and push completed successfully!
pause
