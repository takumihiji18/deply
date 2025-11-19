from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
import os
import shutil

from ..models import Account
from ..database import db


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/{campaign_id}", response_model=List[Account])
async def get_campaign_accounts(campaign_id: str):
    """Получить аккаунты кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign.accounts


@router.post("/{campaign_id}", response_model=Account)
async def add_account(campaign_id: str, account: Account):
    """Добавить аккаунт в кампанию"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверить, не существует ли уже аккаунт с таким именем
    for acc in campaign.accounts:
        if acc.session_name == account.session_name:
            raise HTTPException(
                status_code=400,
                detail="Account with this session name already exists"
            )
    
    campaign.accounts.append(account)
    
    if await db.save_campaign(campaign):
        return account
    
    raise HTTPException(status_code=500, detail="Failed to add account")


@router.put("/{campaign_id}/{session_name}", response_model=Account)
async def update_account(campaign_id: str, session_name: str, account_update: Account):
    """Обновить аккаунт"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Найти и обновить аккаунт
    for i, acc in enumerate(campaign.accounts):
        if acc.session_name == session_name:
            campaign.accounts[i] = account_update
            
            if await db.save_campaign(campaign):
                return account_update
            
            raise HTTPException(status_code=500, detail="Failed to update account")
    
    raise HTTPException(status_code=404, detail="Account not found")


@router.delete("/{campaign_id}/{session_name}")
async def delete_account(campaign_id: str, session_name: str):
    """Удалить аккаунт из кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Найти и удалить аккаунт
    for i, acc in enumerate(campaign.accounts):
        if acc.session_name == session_name:
            campaign.accounts.pop(i)
            
            # Удалить файлы .session и .json
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            sessions_dir = os.path.join(project_root, "data", "sessions")
            
            session_file = os.path.join(sessions_dir, f"{session_name}.session")
            json_file = os.path.join(sessions_dir, f"{session_name}.json")
            
            # Удаляем файлы если они существуют
            if os.path.exists(session_file):
                os.remove(session_file)
                print(f"✓ Удалён файл: {session_file}")
            
            if os.path.exists(json_file):
                os.remove(json_file)
                print(f"✓ Удалён файл: {json_file}")
            
            if await db.save_campaign(campaign):
                return {"status": "deleted"}
            
            raise HTTPException(status_code=500, detail="Failed to delete account")
    
    raise HTTPException(status_code=404, detail="Account not found")


@router.post("/{campaign_id}/upload-session")
async def upload_session(
    campaign_id: str,
    session_file: UploadFile = File(...),
    session_name: str = None
):
    """Загрузить .session файл"""
    print(f"\n{'='*80}")
    print(f"UPLOAD SESSION CALLED: campaign_id={campaign_id}, filename={session_file.filename}")
    print(f"{'='*80}\n")
    
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверить расширение файла
    if not session_file.filename.endswith('.session'):
        raise HTTPException(status_code=400, detail="Only .session files are allowed")
    
    # Определить имя сессии
    if not session_name:
        session_name = session_file.filename.replace('.session', '')
    
    # Определить путь к корню проекта
    # __file__ = backend/app/api/accounts.py -> нужно 4 раза dirname
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    
    print(f"DEBUG: project_root = {project_root}")
    
    # Создать папку для сессий в КОРНЕ проекта
    sessions_dir = os.path.join(project_root, "data", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    
    print(f"DEBUG: sessions_dir = {sessions_dir}")
    print(f"DEBUG: sessions_dir exists = {os.path.exists(sessions_dir)}")
    
    # Сохранить файл
    session_path = os.path.join(sessions_dir, f"{session_name}.session")
    
    try:
        content = await session_file.read()
        print(f"DEBUG: Read {len(content)} bytes from upload")
        
        with open(session_path, 'wb') as f:
            f.write(content)
        
        print(f"✓✓✓ УСПЕШНО ЗАГРУЖЕН .session файл: {session_path} ({len(content)} байт)")
        print(f"✓✓✓ Файл существует: {os.path.exists(session_path)}")
        print(f"✓✓✓ Размер на диске: {os.path.getsize(session_path)} байт\n")
        
        return {
            "status": "uploaded",
            "session_name": session_name,
            "path": session_path
        }
    except Exception as e:
        import traceback
        print(f"✗✗✗ ОШИБКА загрузки .session: {e}")
        print(f"✗✗✗ Traceback: {traceback.format_exc()}\n")
        raise HTTPException(status_code=500, detail=f"Failed to upload session: {str(e)}")


@router.post("/{campaign_id}/upload-json")
async def upload_json(
    campaign_id: str,
    json_file: UploadFile = File(...)
):
    """Загрузить .json файл с настройками аккаунта"""
    print(f"\n{'='*80}")
    print(f"UPLOAD JSON CALLED: campaign_id={campaign_id}, filename={json_file.filename}")
    print(f"{'='*80}\n")
    
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверить расширение файла
    if not json_file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only .json files are allowed")
    
    # Определить имя сессии
    session_name = json_file.filename.replace('.json', '')
    
    # Определить путь к корню проекта
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    
    # Создать папку для сессий в КОРНЕ проекта
    sessions_dir = os.path.join(project_root, "data", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    
    # Сохранить файл
    json_path = os.path.join(sessions_dir, f"{session_name}.json")
    
    try:
        content = await json_file.read()
        
        # Проверить что это валидный JSON
        import json as json_lib
        json_data = json_lib.loads(content.decode('utf-8'))
        
        # Проверить что есть необходимые поля
        api_id = json_data.get('api_id') or json_data.get('app_id')
        api_hash = json_data.get('api_hash') or json_data.get('app_hash')
        
        if not api_id or not api_hash:
            raise HTTPException(
                status_code=400, 
                detail="JSON must contain api_id (or app_id) and api_hash (or app_hash)"
            )
        
        # Сохранить файл
        with open(json_path, 'wb') as f:
            f.write(content)
        
        print(f"✓ Загружен .json файл: {json_path}")
        print(f"  api_id: {api_id}, api_hash: {api_hash[:10]}..., proxy: {json_data.get('proxy', 'нет')}")
        
        return {
            "status": "uploaded",
            "session_name": session_name,
            "path": json_path,
            "api_id": api_id,
            "api_hash": api_hash,  # ← Возвращаем api_hash!
            "proxy": json_data.get('proxy', ''),
            "has_proxy": bool(json_data.get('proxy') and json_data['proxy'] != 'null')
        }
    except json_lib.JSONDecodeError as e:
        print(f"✗ Ошибка парсинга JSON: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        print(f"✗ Ошибка загрузки JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload JSON: {str(e)}")


@router.get("/available")
async def get_available_sessions():
    """Получить список доступных .session файлов"""
    sessions_dir = "data/sessions"
    
    if not os.path.exists(sessions_dir):
        return {"sessions": []}
    
    sessions = []
    for file in os.listdir(sessions_dir):
        if file.endswith('.session'):
            session_name = file.replace('.session', '')
            
            # Проверить, есть ли .json файл с настройками
            json_path = os.path.join(sessions_dir, f"{session_name}.json")
            has_config = os.path.exists(json_path)
            
            sessions.append({
                "session_name": session_name,
                "has_config": has_config
            })
    
    return {"sessions": sessions}

