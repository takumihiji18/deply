from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from typing import Dict, Set
import json

from .api import campaigns, accounts, dialogs
from .campaign_manager import campaign_runner


app = FastAPI(
    title="Telegram Auto-Responder Manager",
    description="Web interface for managing multiple Telegram auto-responder campaigns",
    version="1.0.0"
)

# CORS middleware для React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production указать конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(campaigns.router)
app.include_router(accounts.router)
app.include_router(dialogs.router)


# WebSocket для real-time обновлений
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключенным клиентам"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Удалить отключенные соединения
        self.active_connections -= disconnected


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time обновлений"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Получаем сообщения от клиента (если нужно)
            data = await websocket.receive_text()
            
            # Можно обрабатывать команды от клиента
            try:
                message = json.loads(data)
                # Обработка команд
            except json.JSONDecodeError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def status_broadcaster():
    """Фоновая задача для отправки статуса кампаний"""
    while True:
        try:
            # Собираем статус всех кампаний
            from .database import db
            campaigns = await db.list_campaigns()
            
            status_data = []
            for campaign in campaigns:
                is_running = campaign_runner.is_running(campaign.id)
                status_data.append({
                    "campaign_id": campaign.id,
                    "name": campaign.name,
                    "status": campaign.status,
                    "is_running": is_running,
                    "active_accounts": len([a for a in campaign.accounts if a.is_active])
                })
            
            # Отправляем всем подключенным клиентам
            await manager.broadcast({
                "type": "status_update",
                "campaigns": status_data
            })
        
        except Exception as e:
            print(f"Error in status broadcaster: {e}")
        
        # Обновляем каждые 5 секунд
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    """Запускается при старте приложения"""
    # Запускаем фоновую задачу для broadcast статуса
    asyncio.create_task(status_broadcaster())


@app.on_event("shutdown")
async def shutdown_event():
    """Запускается при остановке приложения"""
    # Останавливаем все запущенные кампании
    from .database import db
    campaigns = await db.list_campaigns()
    
    for campaign in campaigns:
        if campaign_runner.is_running(campaign.id):
            await campaign_runner.stop_campaign(campaign.id)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "Telegram Auto-Responder Manager API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


