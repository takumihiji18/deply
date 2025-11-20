from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
import os
import json

from ..models import Dialog, DialogMessage, ProcessedClient
from ..database import db


class AddProcessedClientRequest(BaseModel):
    user_id: int
    username: Optional[str] = None


router = APIRouter(prefix="/dialogs", tags=["dialogs"])


@router.get("/{campaign_id}", response_model=List[Dialog])
async def get_campaign_dialogs(campaign_id: str):
    """Получить все диалоги кампании"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    dialogs = []
    
    # Преобразуем относительный путь в абсолютный
    work_folder = campaign.work_folder
    if not os.path.isabs(work_folder):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        work_folder = os.path.join(project_root, work_folder)
    
    convos_dir = os.path.join(work_folder, "convos")
    
    if not os.path.exists(convos_dir):
        return dialogs
    
    # Читаем все файлы диалогов
    for filename in os.listdir(convos_dir):
        if filename.endswith('.jsonl'):
            try:
                # Парсим имя файла: sessionname_userid_username.jsonl
                parts = filename.replace('.jsonl', '').split('_')
                
                if len(parts) >= 2:
                    session_name = parts[0]
                    user_id = int(parts[1])
                    username = parts[2] if len(parts) > 2 else None
                    
                    # Читаем сообщения
                    messages = []
                    filepath = os.path.join(convos_dir, filename)
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                msg_data = json.loads(line)
                                messages.append(DialogMessage(
                                    role=msg_data['role'],
                                    content=msg_data['content']
                                ))
                    
                    dialogs.append(Dialog(
                        session_name=session_name,
                        user_id=user_id,
                        username=username,
                        messages=messages
                    ))
            except Exception as e:
                print(f"Error reading dialog {filename}: {e}")
                continue
    
    return dialogs


@router.get("/{campaign_id}/{session_name}/{user_id}", response_model=Dialog)
async def get_dialog(campaign_id: str, session_name: str, user_id: int):
    """Получить конкретный диалог"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    work_folder = campaign.work_folder
    if not os.path.isabs(work_folder):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        work_folder = os.path.join(project_root, work_folder)
    
    convos_dir = os.path.join(work_folder, "convos")
    
    # Попробуем найти файл с или без username
    possible_files = [
        f for f in os.listdir(convos_dir)
        if f.startswith(f"{session_name}_{user_id}") and f.endswith('.jsonl')
    ] if os.path.exists(convos_dir) else []
    
    if not possible_files:
        raise HTTPException(status_code=404, detail="Dialog not found")
    
    filepath = os.path.join(convos_dir, possible_files[0])
    
    # Парсим имя файла для username
    filename = possible_files[0].replace('.jsonl', '')
    parts = filename.split('_')
    username = parts[2] if len(parts) > 2 else None
    
    # Читаем сообщения
    messages = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                msg_data = json.loads(line)
                messages.append(DialogMessage(
                    role=msg_data['role'],
                    content=msg_data['content']
                ))
    
    return Dialog(
        session_name=session_name,
        user_id=user_id,
        username=username,
        messages=messages
    )


@router.delete("/{campaign_id}/{session_name}/{user_id}")
async def delete_dialog(campaign_id: str, session_name: str, user_id: int):
    """Удалить диалог"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    work_folder = campaign.work_folder
    if not os.path.isabs(work_folder):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        work_folder = os.path.join(project_root, work_folder)
    
    convos_dir = os.path.join(work_folder, "convos")
    
    if not os.path.exists(convos_dir):
        raise HTTPException(status_code=404, detail="Dialog not found")
    
    # Найти и удалить файл
    deleted = False
    for filename in os.listdir(convos_dir):
        if filename.startswith(f"{session_name}_{user_id}") and filename.endswith('.jsonl'):
            filepath = os.path.join(convos_dir, filename)
            os.remove(filepath)
            deleted = True
            break
    
    if deleted:
        return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Dialog not found")


@router.get("/{campaign_id}/processed", response_model=List[ProcessedClient])
async def get_processed_clients(campaign_id: str):
    """Получить список обработанных клиентов"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    processed_file = campaign.processed_clients_file
    if not os.path.isabs(processed_file):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        processed_file = os.path.join(project_root, processed_file)
    
    if not os.path.exists(processed_file):
        return []
    
    clients = []
    with open(processed_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Формат: user_id | @username
            parts = line.split('|')
            if len(parts) >= 1:
                try:
                    user_id = int(parts[0].strip())
                    username = parts[1].strip() if len(parts) > 1 else None
                    
                    clients.append(ProcessedClient(
                        user_id=user_id,
                        username=username,
                        campaign_id=campaign_id
                    ))
                except ValueError:
                    continue
    
    return clients


@router.delete("/{campaign_id}/processed/{user_id}")
async def remove_processed_client(campaign_id: str, user_id: int):
    """Удалить клиента из списка обработанных"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    processed_file = campaign.processed_clients_file
    if not os.path.isabs(processed_file):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        processed_file = os.path.join(project_root, processed_file)
    
    if not os.path.exists(processed_file):
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Читаем все строки кроме удаляемой
    lines = []
    found = False
    
    with open(processed_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                parts = line.split('|')
                if parts and int(parts[0].strip()) == user_id:
                    found = True
                    continue
                lines.append(line)
    
    if not found:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Перезаписываем файл
    with open(processed_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    return {"status": "deleted"}


@router.post("/{campaign_id}/processed/add")
async def add_processed_client(campaign_id: str, data: AddProcessedClientRequest):
    """Добавить клиента в список обработанных"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    processed_file = campaign.processed_clients_file
    if not os.path.isabs(processed_file):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        processed_file = os.path.join(project_root, processed_file)
    
    # Проверяем, не добавлен ли уже
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.split('|')
                if parts and int(parts[0].strip()) == data.user_id:
                    raise HTTPException(status_code=400, detail="Client already processed")
    
    # Добавляем клиента
    line = f"{data.user_id} | {data.username if data.username else '(no username)'}"
    with open(processed_file, 'a', encoding='utf-8') as f:
        f.write(line + "\n")
    
    return {"status": "added", "user_id": data.user_id}


@router.post("/{campaign_id}/processed/upload")
async def upload_processed_clients(campaign_id: str, file: UploadFile = File(...)):
    """Загрузить список обработанных клиентов из файла"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    processed_file = campaign.processed_clients_file
    if not os.path.isabs(processed_file):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        processed_file = os.path.join(project_root, processed_file)
    
    # Читаем загруженный файл
    content = await file.read()
    lines = content.decode('utf-8').splitlines()
    
    # Читаем существующие клиенты
    existing_ids = set()
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.split('|')
                if parts:
                    try:
                        existing_ids.add(int(parts[0].strip()))
                    except ValueError:
                        pass
    
    # Добавляем новые клиенты
    added_count = 0
    with open(processed_file, 'a', encoding='utf-8') as f:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Формат может быть: "user_id | @username" или просто "user_id"
            parts = line.split('|')
            try:
                user_id = int(parts[0].strip())
                if user_id not in existing_ids:
                    username = parts[1].strip() if len(parts) > 1 else '(no username)'
                    f.write(f"{user_id} | {username}\n")
                    existing_ids.add(user_id)
                    added_count += 1
            except ValueError:
                continue
    
    return {"status": "uploaded", "added_count": added_count}


@router.post("/{campaign_id}/dialogs/upload")
async def upload_dialog_history(campaign_id: str, file: UploadFile = File(...)):
    """Загрузить историю диалогов из файла .jsonl"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Преобразуем относительный путь в абсолютный
    work_folder = campaign.work_folder
    if not os.path.isabs(work_folder):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        work_folder = os.path.join(project_root, work_folder)
    
    convos_dir = os.path.join(work_folder, "convos")
    os.makedirs(convos_dir, exist_ok=True)
    
    # Сохраняем файл в папку convos
    file_path = os.path.join(convos_dir, file.filename)
    
    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return {"status": "uploaded", "filename": file.filename}


