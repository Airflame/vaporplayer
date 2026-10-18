@echo off
rem Launch VAPORPLAYER with the project's virtual environment.
rem Any arguments (files or folders) are passed through, so you can also
rem drag music onto this file in Explorer.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found in "%~dp0.venv".
    echo Create it with:  python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
