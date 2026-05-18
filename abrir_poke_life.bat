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

python -c "import rich" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencia Rich...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
  )
)

python main.py
echo.
echo Poke Life foi encerrado.
pause
