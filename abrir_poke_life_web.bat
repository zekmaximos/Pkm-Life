@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python nao foi encontrado no PATH.
  echo Instale o Python 3 ou abra o projeto por um terminal com Python disponivel.
  pause
  exit /b 1
)

python -c "import flask" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
  )
)

echo Iniciando Poke Life Web em http://127.0.0.1:5000
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"
python web\app.py

echo.
echo Poke Life Web foi encerrado.
pause
