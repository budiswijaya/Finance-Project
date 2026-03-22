@echo off
echo Starting Data Normalization Backend...
echo.
cd /d %~dp0
/d/Github/.venv/Scripts/python.exe backend/main.py
pause