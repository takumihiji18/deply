import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiofiles
from .models import Campaign, CampaignStatus, TelegramSettings, OpenAISettings


class Database:
    """Простая файловая база данных для кампаний"""
    
    def __init__(self, campaigns_dir: str = "campaigns_metadata"):
        # Преобразуем в абсолютный путь относительно backend/app
        if not os.path.isabs(campaigns_dir):
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            campaigns_dir = os.path.join(project_root, campaigns_dir)
        
        self.campaigns_dir = campaigns_dir
        os.makedirs(campaigns_dir, exist_ok=True)
        print(f"Database initialized: campaigns_dir = {campaigns_dir}")
    
    def _campaign_path(self, campaign_id: str) -> str:
        return os.path.join(self.campaigns_dir, f"{campaign_id}.json")
    
    async def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Получить кампанию по ID"""
        path = self._campaign_path(campaign_id)
        if not os.path.exists(path):
            return None
        
        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
            return Campaign(**data)
        except Exception as e:
            print(f"Error loading campaign {campaign_id}: {e}")
            return None
    
    async def save_campaign(self, campaign: Campaign) -> bool:
        """Сохранить кампанию"""
        try:
            path = self._campaign_path(campaign.id)
            campaign.updated_at = datetime.now()
            
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(campaign.model_dump_json(indent=2))
            return True
        except Exception as e:
            print(f"Error saving campaign {campaign.id}: {e}")
            return False
    
    async def delete_campaign(self, campaign_id: str) -> bool:
        """Удалить кампанию"""
        try:
            path = self._campaign_path(campaign_id)
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting campaign {campaign_id}: {e}")
            return False
    
    async def list_campaigns(self) -> List[Campaign]:
        """Получить список всех кампаний"""
        campaigns = []
        
        if not os.path.exists(self.campaigns_dir):
            return campaigns
        
        for filename in os.listdir(self.campaigns_dir):
            # Пропускаем файлы статусов диалогов и другие служебные файлы
            if not filename.endswith('.json'):
                continue
            if '_dialog_statuses.json' in filename:
                continue
            if filename.startswith('_'):
                continue
                
            campaign_id = filename[:-5]
            campaign = await self.get_campaign(campaign_id)
            if campaign:
                campaigns.append(campaign)
        
        return sorted(campaigns, key=lambda c: c.created_at, reverse=True)
    
    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """Обновить статус кампании"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False
        
        campaign.status = status
        return await self.save_campaign(campaign)


# Singleton instance
db = Database()


