@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" start_offline_exam.py
) else (
    python start_offline_exam.py
)
if errorlevel 1 pause
