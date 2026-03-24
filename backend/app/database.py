import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiofiles
import asyncio
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
        self._file_locks: Dict[str, asyncio.Lock] = {}
        os.makedirs(campaigns_dir, exist_ok=True)
        print(f"Database initialized: campaigns_dir = {campaigns_dir}")
    
    def _campaign_path(self, campaign_id: str) -> str:
        return os.path.join(self.campaigns_dir, f"{campaign_id}.json")

    def _get_lock(self, path: str) -> asyncio.Lock:
        """Возвращает lock для конкретного файла кампании."""
        lock = self._file_locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self._file_locks[path] = lock
        return lock

    def _parse_campaign_json(self, raw_text: str, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Пытается распарсить JSON кампании.
        Если файл содержит несколько JSON-объектов подряд (ошибка "Extra data"),
        извлекает последний валидный объект как наиболее актуальное состояние.
        """
        text = (raw_text or "").strip()
        if not text:
            return None

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError as e:
            decoder = json.JSONDecoder()
            idx = 0
            objects: List[Dict[str, Any]] = []

            while idx < len(text):
                while idx < len(text) and text[idx].isspace():
                    idx += 1
                if idx >= len(text):
                    break

                try:
                    obj, end_idx = decoder.raw_decode(text, idx)
                except json.JSONDecodeError:
                    break

                if isinstance(obj, dict):
                    objects.append(obj)
                idx = end_idx

            if objects:
                print(
                    f"Warning: campaign {campaign_id} JSON contained extra data; "
                    f"recovered {len(objects)} object(s), using the last one."
                )
                return objects[-1]

            print(f"Error loading campaign {campaign_id}: {e}")
            return None
        except Exception as e:
            print(f"Error loading campaign {campaign_id}: {e}")
            return None

    async def _atomic_write(self, path: str, content: str) -> None:
        """Атомарно записывает файл через temp + os.replace."""
        temp_path = f"{path}.tmp"
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        os.replace(temp_path, path)
    
    async def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Получить кампанию по ID"""
        path = self._campaign_path(campaign_id)
        if not os.path.exists(path):
            return None

        lock = self._get_lock(path)
        async with lock:
            try:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    raw = await f.read()

                data = self._parse_campaign_json(raw, campaign_id)
                if data is None:
                    return None

                # Если файл был "склеен", нормализуем его обратно в валидный JSON.
                normalized = json.dumps(data, ensure_ascii=False, indent=2)
                if raw.strip() != normalized.strip():
                    try:
                        await self._atomic_write(path, normalized)
                    except Exception as repair_err:
                        print(f"Warning: failed to normalize campaign {campaign_id}: {repair_err}")

                return Campaign(**data)
            except Exception as e:
                print(f"Error loading campaign {campaign_id}: {e}")
                return None
    
    async def save_campaign(self, campaign: Campaign) -> bool:
        """Сохранить кампанию"""
        path = self._campaign_path(campaign.id)
        lock = self._get_lock(path)

        try:
            campaign.updated_at = datetime.now()
            payload = campaign.model_dump_json(indent=2)

            async with lock:
                await self._atomic_write(path, payload)
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


