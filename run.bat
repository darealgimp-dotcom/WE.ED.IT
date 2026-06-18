@echo off
setlocal enabledelayedexpansion

:menu
cls
echo ======================================================================
echo WE.ED.IT ULTIMATE + DATABASE - Batch System
echo ======================================================================
echo.
echo Wählen Sie eine Option:
echo.
echo  1. Batch-Verarbeitung starten (alle Audiodateien)
echo  2. Batch-Verarbeitung fortsetzen
echo  3. Batch-Verarbeitung neu starten (ohne Fortsetzung)
echo  4. Version anzeigen
echo  5. Beenden
echo.
set /p choice=Ihre Wahl [1-5]: 

if "%choice%"=="1" goto batch
if "%choice%"=="2" goto resume
if "%choice%"=="3" goto no_resume
if "%choice%"=="4" goto version
if "%choice%"=="5" goto exit

echo Ungültige Auswahl. Bitte versuchen Sie es erneut.
pause
goto menu

:batch
python weedit_ultimate_db.py --batch
pause
goto menu

:resume
python weedit_ultimate_db.py --batch --resume
pause
goto menu

:no_resume
python weedit_ultimate_db.py --batch --no-resume
pause
goto menu

:version
python weedit_ultimate_db.py --version
pause
goto menu

:exit
exit
