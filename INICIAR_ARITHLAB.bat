@echo off
cd /d "%~dp0"
echo Iniciando ArithLab+...
call npm install
call npm run install:all
call npm run dev
pause
