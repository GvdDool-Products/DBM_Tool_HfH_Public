@echo off
setlocal

:: ========================================================
:: CONFIGURATION: SET YOUR PUBLIC REPO PATH HERE
:: ========================================================
set "PROD_DIR=C:\Replace\With\Path\To\Public_Repo"
:: ========================================================

echo ========================================================
echo   SAFE DEPLOYMENT TO PUBLIC REPO
echo   From: %CD%
echo   To:   %PROD_DIR%
echo ========================================================
echo.

if not exist "%PROD_DIR%" (
    echo [ERROR] Production directory not found!
    echo.
    echo 1. Right-click this file and choose 'Edit'.
    echo 2. Change 'PROD_DIR' to the actual folder path of your Public Repo.
    echo.
    pause
    exit /b
)

echo You are about to COPY the Codebase to PRODUCTION.
echo.
echo   [COPYING] src/ folder (Logic)
echo   [COPYING] streamlit_app.py
echo   [COPYING] requirements.txt
echo.
echo   [SKIPPING] data/ (Database SAFETY CHECK)
echo   [SKIPPING] .streamlit/secrets.toml (Credentials SAFETY CHECK)
echo.
echo Press any key to proceed...
pause >nul

echo.
echo [1/4] Syncing 'src' directory...
xcopy "src" "%PROD_DIR%\src" /E /I /Y /Q

echo [2/4] Copying main app file...
copy /Y "streamlit_app.py" "%PROD_DIR%\" >nul

echo [3/4] Copying requirements.txt...
copy /Y "requirements.txt" "%PROD_DIR%\" >nul

echo [4/4] Copying config (if present)...
if exist ".streamlit\config.toml" (
    if not exist "%PROD_DIR%\.streamlit" mkdir "%PROD_DIR%\.streamlit"
    copy /Y ".streamlit\config.toml" "%PROD_DIR%\.streamlit\" >nul
)

echo.
echo ========================================================
echo   SUCCESS: FILES COPIED
echo ========================================================
echo Next Steps:
echo   1. Open Terminal in: %PROD_DIR%
echo   2. Run: git status
echo   3. Run: git add .
echo   4. Run: git commit -m "Update Codebase"
echo   5. Run: git push
echo.
pause
