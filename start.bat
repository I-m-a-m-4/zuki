@echo off
cd /d "%~dp0"
echo Starting Zuki Desktop Companion...
.\.venv\Scripts\python.exe -m zuki run
pause
