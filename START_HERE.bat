@echo off
echo ========================================
echo Telegram Auto-Responder Web Interface
echo ========================================
echo.

echo Checking dependencies...
echo.

REM Check backend dependencies
cd backend
python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [!] Backend dependencies not installed!
    echo Installing backend dependencies...
    echo (This may take 1-2 minutes...)
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] Error installing backend dependencies
        pause
        exit /b 1
    )
    echo [+] Backend dependencies installed
) else (
    echo [+] Backend dependencies already installed
)
cd ..

REM Check frontend dependencies
if not exist "frontend\node_modules" (
    echo [!] Frontend dependencies not installed!
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [X] Error installing frontend dependencies
        pause
        exit /b 1
    )
    echo [+] Frontend dependencies installed
    cd ..
) else (
    echo [+] Frontend dependencies already installed
)

echo.
echo ========================================
echo Starting servers...
echo ========================================
echo.

echo Starting Backend server...
start "Backend Server" cmd /k "cd backend && python run.py"

timeout /t 5 /nobreak > nul

echo Starting Frontend server...
start "Frontend Server" cmd /k "cd frontend && npm start"

echo.
echo ========================================
echo Servers are starting!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo IMPORTANT: Do not close Backend and Frontend windows!
echo.
echo To stop: close both server windows.
echo.
pause

