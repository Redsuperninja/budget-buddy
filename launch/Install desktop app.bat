@echo off
rem Double-click to install the built desktop app with Start menu and desktop shortcuts.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\release\install-desktop.ps1" %*
pause
