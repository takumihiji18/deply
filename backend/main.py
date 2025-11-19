#!/usr/bin/env python3
"""
Wrapper для запуска FastAPI приложения из корня backend
"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

