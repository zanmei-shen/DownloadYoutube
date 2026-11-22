@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run: python -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo The app stopped unexpectedly.
    pause
)
