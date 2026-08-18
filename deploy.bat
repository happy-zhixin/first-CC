@echo off
cd /d "%~dp0"
set PROXY=http://127.0.0.1:7897

echo ==========================================
echo   Music Elf - One-click Deploy
echo ==========================================
echo.

echo [1/3] Staging changes...
git -c http.proxy=%PROXY% -c https.proxy=%PROXY% add -A

set MSG=
set /p MSG=[2/3] Commit message (Enter = "update"):
if "%MSG%"=="" set MSG=update
git -c http.proxy=%PROXY% -c https.proxy=%PROXY% commit -m "%MSG%"

echo [3/3] Pushing to GitHub...
git -c http.proxy=%PROXY% -c https.proxy=%PROXY% push origin main

echo.
echo Done! Site updates in 1-2 min:
echo   https://happy-zhixin.github.io/first-CC/
echo.
pause
