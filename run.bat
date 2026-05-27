@echo off
title Drainage Design Tool
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe ddesign_tool\main.py %*
    goto end
)
python ddesign_tool\main.py %*
if errorlevel 9009 python3 ddesign_tool\main.py %*
if errorlevel 9009 py ddesign_tool\main.py %*

:end
pause
