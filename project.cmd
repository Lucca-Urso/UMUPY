@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 project.py %*) || (python project.py %*)
