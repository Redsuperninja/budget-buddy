@echo off
rem Double-click to remove the Budget Buddy app and its shortcuts. Your data folder is kept.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
pause
