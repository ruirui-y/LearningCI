@echo off
setlocal
cd /d "%~dp0"
if not exist data\learningci.db (
  echo No local database found.
  pause
  exit /b 0
)

echo.
echo WARNING: this deletes local LearningCI runtime state.
echo Use this only when upgrading the early MVP before real learning history matters.
echo.
set /p CONFIRM=Type RESET to continue: 
if /I not "%CONFIRM%"=="RESET" (
  echo Cancelled.
  pause
  exit /b 1
)
copy /Y data\learningci.db data\learningci.backup.db >nul
del /Q data\learningci.db
echo Old database backed up to data\learningci.backup.db
echo Local state reset. Start LearningCI again to import the corrected frozen plan.
pause
