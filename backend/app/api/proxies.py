from fastapi import APIRouter, HTTPException
from typing import List
import uuid

from ..models import ProxyItem
from ..database import db


router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("/{campaign_id}", response_model=List[ProxyItem])
async def get_campaign_proxies(campaign_id: str):
    """Получить список прокси кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign.proxies


@router.post("/{campaign_id}", response_model=ProxyItem)
async def add_proxy(campaign_id: str, proxy_url: str, proxy_name: str = None):
    """Добавить новый прокси в кампанию"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверить, не существует ли уже прокси с таким URL
    for proxy in campaign.proxies:
        if proxy.url == proxy_url:
            raise HTTPException(
                status_code=400,
                detail="Proxy with this URL already exists"
            )
    
    # Создать новый прокси
    new_proxy = ProxyItem(
        id=str(uuid.uuid4()),
        url=proxy_url,
        name=proxy_name,
        is_active=True
    )
    
    campaign.proxies.append(new_proxy)
    
    if await db.save_campaign(campaign):
        return new_proxy
    
    raise HTTPException(status_code=500, detail="Failed to add proxy")


@router.put("/{campaign_id}/{proxy_id}", response_model=ProxyItem)
async def update_proxy(campaign_id: str, proxy_id: str, proxy_url: str, proxy_name: str = None):
    """Обновить прокси"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Найти и обновить прокси
    for i, proxy in enumerate(campaign.proxies):
        if proxy.id == proxy_id:
            campaign.proxies[i].url = proxy_url
            campaign.proxies[i].name = proxy_name
            
            if await db.save_campaign(campaign):
                return campaign.proxies[i]
            
            raise HTTPException(status_code=500, detail="Failed to update proxy")
    
    raise HTTPException(status_code=404, detail="Proxy not found")


@router.delete("/{campaign_id}/{proxy_id}")
async def delete_proxy(campaign_id: str, proxy_id: str):
    """Удалить прокси из кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Найти и удалить прокси
    for i, proxy in enumerate(campaign.proxies):
        if proxy.id == proxy_id:
            # Удалить привязки этого прокси у аккаунтов
            for account in campaign.accounts:
                if account.proxy_id == proxy_id:
                    account.proxy_id = None
                    account.proxy = None
            
            campaign.proxies.pop(i)
            
            if await db.save_campaign(campaign):
                return {"status": "deleted"}
            
            raise HTTPException(status_code=500, detail="Failed to delete proxy")
    
    raise HTTPException(status_code=404, detail="Proxy not found")


@router.delete("/{campaign_id}")
async def clear_all_proxies(campaign_id: str):
    """Очистить все прокси кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Удалить все привязки прокси у аккаунтов
    for account in campaign.accounts:
        account.proxy_id = None
        account.proxy = None
    
    # Очистить список прокси
    campaign.proxies = []
    
    if await db.save_campaign(campaign):
        return {"status": "cleared", "count": 0}
    
    raise HTTPException(status_code=500, detail="Failed to clear proxies")


@router.post("/{campaign_id}/bulk")
async def add_bulk_proxies(campaign_id: str, proxies_text: str):
    """
    Массовое добавление прокси из текста (каждый прокси с новой строки)
    """
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Разбить текст на строки и очистить
    proxy_lines = [line.strip() for line in proxies_text.split('\n') if line.strip()]
    
    added_count = 0
    skipped_count = 0
    
    for proxy_url in proxy_lines:
        # Проверить, не существует ли уже прокси с таким URL
        exists = any(p.url == proxy_url for p in campaign.proxies)
        if exists:
            skipped_count += 1
            continue
        
        # Создать новый прокси
        new_proxy = ProxyItem(
            id=str(uuid.uuid4()),
            url=proxy_url,
            is_active=True
        )
        
        campaign.proxies.append(new_proxy)
        added_count += 1
    
    if await db.save_campaign(campaign):
        return {
            "status": "success",
            "added": added_count,
            "skipped": skipped_count,
            "total": len(campaign.proxies)
        }
    
    raise HTTPException(status_code=500, detail="Failed to add proxies")


@router.get("/{campaign_id}/usage")
async def get_proxy_usage(campaign_id: str):
    """
    Получить статистику использования прокси (сколько аккаунтов привязано к каждому)
    """
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Подсчитать использование каждого прокси
    usage = {}
    for proxy in campaign.proxies:
        usage[proxy.id] = {
            "proxy": proxy,
            "accounts_count": 0,
            "accounts": []
        }
    
    # Подсчитать аккаунты для каждого прокси
    for account in campaign.accounts:
        if account.proxy_id and account.proxy_id in usage:
            usage[account.proxy_id]["accounts_count"] += 1
            usage[account.proxy_id]["accounts"].append(account.session_name)
    
    return {"usage": list(usage.values())}

