@echo off
echo Starting Telegram Auto-Responder Web Interface...
echo.
echo Opening Backend in new window...
start "Backend Server" cmd /k "cd backend && python run.py"

timeout /t 3 /nobreak > nul

echo Opening Frontend in new window...
start "Frontend Server" cmd /k "cd frontend && npm start"

echo.
echo Both servers are starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to exit (servers will keep running)...
pause > nul


