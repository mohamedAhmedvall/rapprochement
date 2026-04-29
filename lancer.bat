@echo off
REM Copilote d'Encaissement — lancement Windows
title Copilote d'Encaissement (Veolia / SOMEI)

cd /d "%~dp0"

REM Vérifie Python
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo ERREUR : Python n'est pas dans le PATH.
  echo Installer Python 3.9+ depuis https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

REM Vérifie openpyxl, l'installe si manquant
python -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
  echo Installation de openpyxl...
  python -m pip install --quiet openpyxl
)

REM Lance l'application
python rapprochement_app_V6.py
