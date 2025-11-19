#!/bin/bash

echo "========================================"
echo "Installing Telegram Auto-Responder"
echo "Web Interface Dependencies"
echo "========================================"
echo ""

echo "Installing Backend dependencies..."
cd backend
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install backend dependencies"
    exit 1
fi
cd ..

echo ""
echo "Installing Frontend dependencies..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install frontend dependencies"
    exit 1
fi
cd ..

echo ""
echo "========================================"
echo "Installation completed successfully!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Run ./start_all.sh to start both servers"
echo "2. Open http://localhost:3000 in your browser"
echo ""


