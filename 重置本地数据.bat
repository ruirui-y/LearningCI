@echo off
setlocal
cd /d "%~dp0"
if not exist data\learningci.db (
  echo No local database found.
  pause
  exit /b 0
)

echo.
echo WARNING: this resets only the local runtime database.
echo sync\learningci.db will NOT be deleted.
echo.
set /p CONFIRM=Type RESET to continue: 
if /I not "%CONFIRM%"=="RESET" (
  echo Cancelled.
  pause
  exit /b 1
)
copy /Y data\learningci.db data\learningci.backup.db >nul
del /Q data\learningci.db
if exist data\learningci.db-wal del /Q data\learningci.db-wal
if exist data\learningci.db-shm del /Q data\learningci.db-shm
echo Old local database backed up to data\learningci.backup.db
echo Local state reset. If sync\learningci.db exists, next start will restore it automatically.
pause
