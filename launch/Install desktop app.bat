@echo off
rem Double-click to install the built desktop app with Start menu and desktop shortcuts.
call "%~dp0..\scripts\run-python.bat" scripts\release\install_desktop.py %*
pause
