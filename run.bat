@echo off
cd /d "%~dp0"
python pomodoro.py
if errorlevel 1 pause
