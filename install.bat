@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Создаю окружение Python и ставлю библиотеки...
python -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo Готово. Запуск: start.bat
pause
