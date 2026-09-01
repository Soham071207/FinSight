

@echo off
echo ===================================================
echo   FinSight Startup Script (Backend + Frontend)
echo ===================================================
echo.

echo Starting Mutual Fund API Server (Port 5050) in a new window...
start "Mutual Fund Server (Port 5050)" cmd /k "python mutual_2_api.py"

echo Starting Stock Prediction API Server (Port 5051) in a new window...
start "Stock Analysis Server (Port 5051)" cmd /k "cd STOCK && python stock_api.py"

echo Starting Flutter Web App in a new window...
start "Flutter Web App" cmd /k "flutter run -d chrome --web-port 3000"

echo.
echo All servers (Mutual Fund, Stock Analysis, and Flutter Web) are starting!
echo Keep the new windows open while using FinSight.
echo You can safely close this script window.
pause
