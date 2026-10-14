@echo off
rem Double-click to build the Budget Buddy desktop app into this folder ("Budget Buddy").
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\release\build-desktop.ps1" %*
pause
