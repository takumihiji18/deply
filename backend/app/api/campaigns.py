from fastapi import APIRouter, HTTPException, status
from typing import List
import uuid
import os
from datetime import datetime

from ..models import (
    Campaign, CampaignCreate, CampaignUpdate, CampaignStatus,
    CampaignStats, TelegramSettings
)
from ..database import db
from ..campaign_manager import campaign_runner


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/", response_model=List[Campaign])
async def list_campaigns():
    """Получить список всех кампаний"""
    return await db.list_campaigns()


@router.post("/", response_model=Campaign, status_code=status.HTTP_201_CREATED)
async def create_campaign(campaign_data: CampaignCreate):
    """Создать новую кампанию"""
    # Генерируем ID
    campaign_id = str(uuid.uuid4())
    
    # Определить путь к корню проекта
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    
    # Создаем директорию для кампании (АБСОЛЮТНЫЙ путь)
    # ВАЖНО: Используем campaigns_runtime - там же где main.py работает!
    campaign_dir = os.path.join(project_root, "campaigns_runtime", campaign_id)
    work_folder = os.path.join(campaign_dir, "data")
    processed_file = os.path.join(campaign_dir, "processed_clients.txt")
    
    # Создаем директории
    os.makedirs(work_folder, exist_ok=True)
    
    # Применяем дефолтные telegram настройки если не переданы
    telegram_settings = campaign_data.telegram_settings or TelegramSettings()
    
    campaign = Campaign(
        id=campaign_id,
        name=campaign_data.name,
        status=CampaignStatus.STOPPED,
        accounts=[],
        openai_settings=campaign_data.openai_settings,
        telegram_settings=telegram_settings,
        work_folder=work_folder,
        processed_clients_file=processed_file
    )
    
    if await db.save_campaign(campaign):
        # Создаем файл processed_clients.txt с дефолтными ботами
        if not os.path.exists(processed_file):
            with open(processed_file, 'w', encoding='utf-8') as f:
                f.write("178220800 | SpamBot\n")
                f.write("5314653481 | PremiumBot\n")
        return campaign
    
    raise HTTPException(status_code=500, detail="Failed to create campaign")


@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(campaign_id: str):
    """Получить кампанию по ID"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.put("/{campaign_id}", response_model=Campaign)
async def update_campaign(campaign_id: str, updates: CampaignUpdate):
    """Обновить кампанию"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Применяем обновления
    if updates.name is not None:
        campaign.name = updates.name
    if updates.status is not None:
        campaign.status = updates.status
    if updates.accounts is not None:
        campaign.accounts = updates.accounts
    if updates.openai_settings is not None:
        campaign.openai_settings = updates.openai_settings
    if updates.telegram_settings is not None:
        campaign.telegram_settings = updates.telegram_settings
    if updates.proxy_list is not None:
        campaign.proxy_list = updates.proxy_list
    
    if await db.save_campaign(campaign):
        return campaign
    
    raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """Удалить кампанию"""
    # Остановить если запущена
    if campaign_runner.is_running(campaign_id):
        await campaign_runner.stop_campaign(campaign_id)
    
    if await db.delete_campaign(campaign_id):
        return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Campaign not found")


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """Запустить кампанию"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign_runner.is_running(campaign_id):
        raise HTTPException(status_code=400, detail="Campaign already running")
    
    if await campaign_runner.start_campaign(campaign_id):
        return {"status": "started"}
    
    raise HTTPException(status_code=500, detail="Failed to start campaign")


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    """Остановить кампанию"""
    if await campaign_runner.stop_campaign(campaign_id):
        return {"status": "stopped"}
    
    raise HTTPException(status_code=500, detail="Failed to stop campaign")


@router.get("/{campaign_id}/status")
async def get_campaign_status(campaign_id: str):
    """Получить статус кампании"""
    try:
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        is_running = campaign_runner.is_running(campaign_id)
        
        return {
            "campaign_id": campaign_id,
            "status": campaign.status,
            "is_running": is_running,
            "updated_at": campaign.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        # Логируем ошибку и возвращаем безопасный ответ
        print(f"ERROR in get_campaign_status: {e!r}")
        return {
            "campaign_id": campaign_id,
            "status": "unknown",
            "is_running": False,
            "error": str(e)
        }


@router.get("/{campaign_id}/logs")
async def get_campaign_logs(campaign_id: str, limit: int = 100):
    """Получить логи кампании"""
    logs = await campaign_runner.get_campaign_logs(campaign_id, limit)
    return {"logs": logs}


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(campaign_id: str):
    """Получить статистику кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # TODO: Implement actual stats collection
    stats = CampaignStats(
        campaign_id=campaign_id,
        total_dialogs=0,
        total_processed=0,
        active_sessions=len([a for a in campaign.accounts if a.is_active]),
        status=campaign.status,
        last_activity=campaign.updated_at
    )
    
    return stats


@router.post("/{campaign_id}/fix-paths")
async def fix_campaign_paths(campaign_id: str):
    """ВРЕМЕННЫЙ эндпоинт для исправления путей старой кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Определить корень проекта
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    
    # Новые пути
    campaign_dir = os.path.join(project_root, "campaigns_runtime", campaign_id)
    work_folder = os.path.join(campaign_dir, "data")
    processed_file = os.path.join(campaign_dir, "processed_clients.txt")
    
    # Обновляем пути
    old_work_folder = campaign.work_folder
    old_processed_file = campaign.processed_clients_file
    
    campaign.work_folder = work_folder
    campaign.processed_clients_file = processed_file
    
    if await db.save_campaign(campaign):
        return {
            "status": "fixed",
            "old_paths": {
                "work_folder": old_work_folder,
                "processed_file": old_processed_file
            },
            "new_paths": {
                "work_folder": work_folder,
                "processed_file": processed_file
            }
        }
    
    raise HTTPException(status_code=500, detail="Failed to update paths")


