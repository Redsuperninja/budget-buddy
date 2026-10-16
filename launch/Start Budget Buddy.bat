@echo off
rem Double-click to start Budget Buddy. Close the window that opens to stop it.
call "%~dp0..\scripts\run-python.bat" scripts\start.py %*
if errorlevel 1 pause
