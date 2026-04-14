@echo off
echo Starting Git Push Process...
echo ============================

echo.
echo Adding all changes...
git add .

echo.
git status

echo.
set /p desc="Enter commit message (or press Enter to use default 'Update Geo-Intel pipeline'): "
if "%desc%"=="" set desc="Update Geo-Intel pipeline"

echo.
echo Committing changes...
git commit -m "%desc%"

echo.
echo Pushing to remote repository...
git push origin main

echo.
echo Done! Press any key to exit.
pause > nul
