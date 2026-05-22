@echo off
title Poke Life
cd /d "%~dp0"

echo Verificando dependencias...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Instalando Flask...
    pip install flask --quiet
)

echo.
echo  PokeLife iniciando em http://localhost:5000
echo  Pressione Ctrl+C para encerrar.
echo.

start "" http://localhost:5000
python -m web.app
pause
