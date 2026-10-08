@echo off
rem Double-click to start Budget Buddy. Close the window that opens to stop it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\start.ps1" %*
if errorlevel 1 pause
