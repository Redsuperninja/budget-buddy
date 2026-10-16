@echo off
rem Run a Budget Buddy script with Python 3.12 or newer, on Windows. The double-click files in launch\ use it:
rem   call scripts\run-python.bat scripts\start.py [arguments]
rem Paths are relative to the Budget Buddy folder, wherever this is run from.

cd /d "%~dp0.."
where py >nul 2>nul
if not errorlevel 1 (
    py -3 %*
    exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
    python %*
    exit /b
)
echo Budget Buddy needs Python 3.12 or newer. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then try again.
exit /b 1
