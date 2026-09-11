@echo off
title Promati Batch Menu
cd /d C:\ai-platform

set DATABASE_URL=postgresql://postgres:SterkWachtwoord123@localhost:15432/promati
set DB_URL=%DATABASE_URL%
set BaseUrl=http://localhost:8000

if not exist logs mkdir logs

ROOT_PATH = r"C:\Users\John Koenders\Baucotech\Logbooks - Documenten\Onderhouds Logboeken - Rapport Entretiens\NL\TATA steel"
python promati_batch_menu.py

echo.
echo Menu afgesloten.
pause