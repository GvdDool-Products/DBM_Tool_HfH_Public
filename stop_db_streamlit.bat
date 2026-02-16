@echo off
echo Stopping all Python processes (Streamlit)...
taskkill /IM python.exe /F
echo.
echo If you saw "SUCCESS", the application has been stopped.
pause
