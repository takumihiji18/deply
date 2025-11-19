#!/usr/bin/env python3
"""
Точка входа для запуска FastAPI backend сервера
"""
import sys
import asyncio
import uvicorn

# Установить правильный event loop для Windows ПЕРЕД запуском
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Отключен reload для стабильной работы
        log_level="info"
    )

