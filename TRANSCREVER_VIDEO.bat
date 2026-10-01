@echo off
rem Arraste um ou mais videos em cima deste arquivo (ou de um atalho para ele).
rem Cria, ao lado de cada video, a pasta com os quadros, a transcricao e o roteiro.
setlocal
chcp 65001 >nul
set "PASTA=%~dp0"
set "PY=%PASTA%venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Ambiente Python nao encontrado em "%PY%".
  echo Na pasta da skill, rode:
  echo   python -m venv venv
  echo   venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if "%~1"=="" (
  echo Arraste um ou mais videos em cima deste arquivo.
  pause
  exit /b 1
)

:proximo
if "%~1"=="" goto fim
echo.
echo ===== %~nx1 =====
"%PY%" "%PASTA%transcrever_video.py" "%~1"
shift
goto proximo

:fim
echo.
echo Pronto. Abra a pasta com o nome do video e comece pelo 00-ROTEIRO.md
pause
