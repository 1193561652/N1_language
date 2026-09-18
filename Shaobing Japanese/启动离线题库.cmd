@echo off
chcp 65001 >nul
cd /d "%~dp0"
python start_offline_exam.py
if errorlevel 1 pause
