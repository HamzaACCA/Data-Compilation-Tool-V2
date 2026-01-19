@echo off
color 0C
title Clean Old Build Files

echo.
echo ============================================================
echo           CLEANING OLD BUILD FILES
echo ============================================================
echo.
echo This will delete:
echo   - dist folder (old executable)
echo   - build folder (temporary build files)
echo   - installer_output folder (old installer)
echo.
echo Your source code will NOT be deleted!
echo.
pause

echo.
echo Deleting old build files...
echo.

if exist "dist" (
    echo Deleting dist folder...
    rmdir /s /q dist
    echo   OK: dist deleted
) else (
    echo   SKIP: dist folder not found
)

if exist "build" (
    echo Deleting build folder...
    rmdir /s /q build
    echo   OK: build deleted
) else (
    echo   SKIP: build folder not found
)

if exist "installer_output" (
    echo Deleting installer_output folder...
    rmdir /s /q installer_output
    echo   OK: installer_output deleted
) else (
    echo   SKIP: installer_output folder not found
)

echo.
echo ============================================================
echo           CLEANUP COMPLETE!
echo ============================================================
echo.
echo Old build files have been deleted.
echo.
echo Next step: Rebuild the installer
echo   Run: FIX_AND_BUILD.bat
echo.
pause
