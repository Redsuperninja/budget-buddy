@echo off
rem Double-click to build the Budget Buddy desktop app into this folder ("Budget Buddy").
call "%~dp0..\scripts\run-python.bat" scripts\release\build_desktop.py %*
pause
