"""
Dialogs API - управление диалогами кампаний
"""
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from datetime import datetime
from html import escape as html_escape
from urllib.parse import quote, urlparse

from ..models import Dialog, DialogMessage, ProcessedClient, DialogStatus
from ..database import db

# Импорты для отправки сообщений через Telethon
try:
    from telethon import TelegramClient
    from telethon.errors import RPCError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

try:
    from python_socks import ProxyType
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    ProxyType = None


class AddProcessedClientRequest(BaseModel):
    user_id: int
    username: Optional[str] = None


class UpdateDialogStatusRequest(BaseModel):
    status: DialogStatus


class SendMessageRequest(BaseModel):
    """Запрос на отправку сообщения"""
    message: str


router = APIRouter(prefix="/dialogs", tags=["dialogs"])


def _get_statuses_dir() -> str:
    """Возвращает директорию для хранения статусов диалогов"""
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    statuses_dir = os.path.join(project_root, "campaigns_metadata")
    os.makedirs(statuses_dir, exist_ok=True)
    return statuses_dir


def _get_statuses_file(campaign_id: str) -> str:
    """Возвращает путь к файлу статусов диалогов для кампании"""
    return os.path.join(_get_statuses_dir(), f"{campaign_id}_dialog_statuses.json")


def _load_dialog_statuses(campaign_id: str) -> dict:
    """Загружает статусы диалогов из файла"""
    statuses_file = _get_statuses_file(campaign_id)
    if os.path.exists(statuses_file):
        try:
            with open(statuses_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading dialog statuses: {e}")
    return {}


def _save_dialog_statuses(campaign_id: str, statuses: dict):
    """Сохраняет статусы диалогов в файл"""
    statuses_file = _get_statuses_file(campaign_id)
    try:
        with open(statuses_file, 'w', encoding='utf-8') as f:
            json.dump(statuses, f, ensure_ascii=False, indent=2)
        print(f"Saved dialog statuses to {statuses_file}")
            except Exception as e:
        print(f"Error saving dialog statuses: {e}")


def _get_dialog_key(session_name: str, user_id: int) -> str:
    """Возвращает ключ для диалога"""
    return f"{session_name}_{user_id}"


def _get_file_modification_time(filepath: str) -> Optional[datetime]:
    """Возвращает время последней модификации файла"""
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime)
    except:
        return None


# ============================================================
# ВАЖНО: Роуты с /processed/ должны быть ПЕРЕД общими роутами
# иначе FastAPI интерпретирует "processed" как session_name
# ============================================================

@router.get("/{campaign_id}/processed", response_model=List[ProcessedClient])
async def get_processed_clients(campaign_id: str):
    """Получить список обработанных клиентов"""
    try:
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
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in get_processed_clients: {e!r}")
        return []


@router.delete("/{campaign_id}/processed/{user_id}")
async def remove_processed_client(campaign_id: str, user_id: int):
    """Удалить клиента из списка обработанных"""
    try:
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Преобразуем относительный путь в абсолютный
        processed_file = campaign.processed_clients_file
        if not os.path.isabs(processed_file):
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            processed_file = os.path.join(project_root, processed_file)
        
        print(f"DELETE processed client {user_id} from {processed_file}")
        
        if not os.path.exists(processed_file):
            print(f"File not found: {processed_file}")
            raise HTTPException(status_code=404, detail="Processed clients file not found")
        
        # Читаем все строки кроме удаляемой
        lines = []
        found = False
        
        with open(processed_file, 'r', encoding='utf-8') as f:
            for line in f:
                line_content = line.strip()
                if not line_content:
                    continue
                
                try:
                    parts = line_content.split('|')
                    if parts and parts[0].strip():
                        current_user_id = int(parts[0].strip())
                        if current_user_id == user_id:
                            found = True
                            print(f"Found client {user_id}, removing...")
                            continue
                    
                    lines.append(line)
                except ValueError:
                    print(f"Warning: invalid line format: {line_content}")
                    lines.append(line)
        
        if not found:
            print(f"Client {user_id} not found in file")
            raise HTTPException(status_code=404, detail=f"Client {user_id} not found in processed list")
        
        # Перезаписываем файл
        with open(processed_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"Successfully removed client {user_id}")
        return {"status": "deleted", "user_id": user_id}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in remove_processed_client: {e!r}")
        raise HTTPException(status_code=500, detail=f"Failed to remove client: {str(e)}")


@router.post("/{campaign_id}/processed/add")
async def add_processed_client(campaign_id: str, data: AddProcessedClientRequest):
    """Добавить клиента в список обработанных"""
    try:
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Преобразуем относительный путь в абсолютный
        processed_file = campaign.processed_clients_file
        if not os.path.isabs(processed_file):
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            processed_file = os.path.join(project_root, processed_file)
        
        # Создаём файл если не существует
        if not os.path.exists(processed_file):
            os.makedirs(os.path.dirname(processed_file), exist_ok=True)
            with open(processed_file, 'w', encoding='utf-8') as f:
                f.write("")
        
        # Проверяем, не добавлен ли уже
        with open(processed_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.split('|')
                if parts and int(parts[0].strip()) == data.user_id:
                    raise HTTPException(status_code=400, detail="Client already processed")
        
        # Добавляем клиента
        line = f"{data.user_id} | {data.username if data.username else '(no username)'}"
        with open(processed_file, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
        
        print(f"Added processed client {data.user_id}")
        return {"status": "added", "user_id": data.user_id}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in add_processed_client: {e!r}")
        raise HTTPException(status_code=500, detail=f"Failed to add client: {str(e)}")


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


@router.put("/{campaign_id}/status/{session_name}/{user_id}")
async def update_dialog_status(
    campaign_id: str, 
    session_name: str, 
    user_id: int, 
    data: UpdateDialogStatusRequest
):
    """Обновить статус диалога (лид/не лид/потом)"""
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Загружаем статусы (используем campaign_id для надёжности)
    statuses = _load_dialog_statuses(campaign_id)
    
    # Обновляем статус
    dialog_key = _get_dialog_key(session_name, user_id)
    statuses[dialog_key] = data.status.value
    
    # Сохраняем
    _save_dialog_statuses(campaign_id, statuses)
    
    return {"status": "updated", "dialog_key": dialog_key, "new_status": data.status.value}


# ============================================================
# Экспорт и импорт диалогов (ПЕРЕД общими роутами!)
# ============================================================

def _generate_html_export(dialogs: list, campaign_name: str) -> str:
    """Генерирует компактный HTML для экспорта диалогов"""
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Диалоги - {html_escape(campaign_name)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa; 
            padding: 10px;
            line-height: 1.4;
            font-size: 13px;
        }}
        .header {{
            background: #667eea;
            color: white;
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 16px; }}
        .header .meta {{ font-size: 11px; opacity: 0.9; }}
        .dialog {{
            background: white;
            border-radius: 6px;
            margin-bottom: 8px;
            border: 1px solid #e0e0e0;
        }}
        .dialog-header {{
            background: #f8f9fa;
            padding: 8px 12px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }}
        .dialog-header .user {{ font-weight: 600; color: #333; }}
        .dialog-header .account {{ color: #888; font-size: 11px; }}
        .dialog-header .status {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 500;
        }}
        .status-lead {{ background: #d4edda; color: #155724; }}
        .status-not_lead {{ background: #f8d7da; color: #721c24; }}
        .status-later {{ background: #fff3cd; color: #856404; }}
        .status-none {{ background: #e9ecef; color: #6c757d; }}
        .messages {{ padding: 8px 12px; }}
        .message {{
            max-width: 85%;
            padding: 6px 10px;
            border-radius: 10px;
            margin-bottom: 4px;
            font-size: 12px;
        }}
        .message.user {{
            background: #e3f2fd;
            color: #1565c0;
        }}
        .message.assistant {{
            background: #f0f0f0;
            color: #333;
            margin-left: auto;
        }}
        .message-label {{
            font-size: 9px;
            font-weight: 600;
            opacity: 0.6;
            margin-bottom: 2px;
        }}
        .summary {{
            background: white;
            border-radius: 6px;
            padding: 12px;
            margin-top: 15px;
            border: 1px solid #e0e0e0;
        }}
        .summary h3 {{ font-size: 14px; color: #333; margin-bottom: 10px; }}
        .summary .stats {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }}
        .summary .stat {{ text-align: center; }}
        .summary .stat-value {{ font-size: 18px; font-weight: 700; color: #667eea; }}
        .summary .stat-label {{ font-size: 10px; color: #888; }}
        @media print {{
            body {{ padding: 5px; }}
            .dialog {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📬 {html_escape(campaign_name)}</h1>
        <div class="meta">{datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
    </div>
"""
    
    total_messages = 0
    leads_count = 0
    not_leads_count = 0
    
    for dialog in dialogs:
        status = dialog.get('status', 'none')
        status_labels = {
            'lead': '✅ Лид',
            'not_lead': '❌ Не лид',
            'later': '⏰ Потом',
            'none': '—'
        }
        status_label = status_labels.get(status, '—')
        
        if status == 'lead':
            leads_count += 1
        elif status == 'not_lead':
            not_leads_count += 1
        
        username = dialog.get('username', '')
        user_display = f"@{username}" if username else f"ID: {dialog.get('user_id', 'N/A')}"
        
        html += f"""<div class="dialog">
<div class="dialog-header">
<span class="user">{html_escape(user_display)}</span>
<span class="account">{html_escape(dialog.get('session_name', 'N/A'))}</span>
<span class="status status-{status}">{status_label}</span>
</div>
<div class="messages">"""
        
        messages = dialog.get('messages', [])
        total_messages += len(messages)
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = html_escape(msg.get('content', ''))
            label = '👤' if role == 'user' else '🤖'
            
            html += f"""<div class="message {role}"><span class="message-label">{label}</span> {content}</div>"""
        
        html += """</div></div>
"""
    
    html += f"""<div class="summary">
<h3>📊 Итого</h3>
<div class="stats">
<div class="stat"><div class="stat-value">{len(dialogs)}</div><div class="stat-label">Диалогов</div></div>
<div class="stat"><div class="stat-value">{total_messages}</div><div class="stat-label">Сообщений</div></div>
<div class="stat"><div class="stat-value">{leads_count}</div><div class="stat-label">Лидов</div></div>
<div class="stat"><div class="stat-value">{not_leads_count}</div><div class="stat-label">Не лидов</div></div>
</div></div>
</body></html>"""
    
    return html


def _sanitize_filename(name: str) -> str:
    """Очищает имя файла от небезопасных символов"""
    import re
    # Заменяем небезопасные символы на подчёркивания
    safe_name = re.sub(r'[^\w\-.]', '_', name)
    # Убираем множественные подчёркивания
    safe_name = re.sub(r'_+', '_', safe_name)
    return safe_name.strip('_')


@router.get("/{campaign_id}/export/{format}")
async def export_dialogs(campaign_id: str, format: str):
    """
    Экспортировать все диалоги кампании.
    format: 'json' или 'html'
    """
    try:
        if format not in ['json', 'html']:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'html'")
        
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Получаем все диалоги
        dialogs_data = []
        
        # Преобразуем относительный путь в абсолютный
        work_folder = campaign.work_folder
        if not os.path.isabs(work_folder):
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            work_folder = os.path.join(project_root, work_folder)
        
        convos_dir = os.path.join(work_folder, "convos")
        
        if os.path.exists(convos_dir):
            # Загружаем статусы
            statuses = _load_dialog_statuses(campaign_id)
            
            for filename in os.listdir(convos_dir):
                if filename.endswith('.jsonl'):
                    try:
                        parts = filename.replace('.jsonl', '').split('_', 2)
                        if len(parts) >= 2:
                            session_name = parts[0]
                            user_id = int(parts[1])
                            username = parts[2] if len(parts) > 2 else None
                            
                            messages = []
                            filepath = os.path.join(convos_dir, filename)
                            
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip():
                                        try:
                                            msg_data = json.loads(line)
                                            messages.append({
                                                'role': msg_data.get('role', 'user'),
                                                'content': msg_data.get('content', '')
                                            })
                                        except json.JSONDecodeError:
                                            continue
                            
                            dialog_key = f"{session_name}_{user_id}"
                            status = statuses.get(dialog_key, 'none')
                            
                            dialogs_data.append({
                                'session_name': session_name,
                                'user_id': user_id,
                                'username': username,
                                'status': status,
                                'messages': messages
                            })
                    except Exception as e:
                        print(f"Error reading dialog {filename}: {e}")
                        continue
        
        # Сортируем по количеству сообщений (больше = выше)
        dialogs_data.sort(key=lambda d: len(d['messages']), reverse=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Используем безопасное имя файла
        safe_campaign_name = _sanitize_filename(campaign.name)
        
        if format == 'json':
            export_data = {
                'campaign_id': campaign_id,
                'campaign_name': campaign.name,
                'exported_at': datetime.now().isoformat(),
                'total_dialogs': len(dialogs_data),
                'dialogs': dialogs_data
            }
            
            content = json.dumps(export_data, ensure_ascii=False, indent=2)
            export_filename = f"dialogs_{safe_campaign_name}_{timestamp}.json"
            
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{export_filename}"; filename*=UTF-8\'\'{export_filename}'
                }
            )
        
        else:  # html
            html_content = _generate_html_export(dialogs_data, campaign.name)
            export_filename = f"dialogs_{safe_campaign_name}_{timestamp}.html"
            
            return Response(
                content=html_content,
                media_type="text/html; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{export_filename}"; filename*=UTF-8\'\'{export_filename}'
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Export error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/{campaign_id}/import")
async def import_dialogs(campaign_id: str, file: UploadFile = File(...)):
    """
    Импортировать диалоги из JSON файла.
    Формат файла должен соответствовать экспорту.
    """
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be JSON format")
    
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Проверяем структуру
    if 'dialogs' not in data:
        raise HTTPException(status_code=400, detail="Invalid format: 'dialogs' field required")
    
    # Преобразуем относительный путь в абсолютный
    work_folder = campaign.work_folder
    if not os.path.isabs(work_folder):
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        work_folder = os.path.join(project_root, work_folder)
    
    convos_dir = os.path.join(work_folder, "convos")
    os.makedirs(convos_dir, exist_ok=True)
    
    imported_count = 0
    skipped_count = 0
    
    # Загружаем существующие статусы
    statuses = _load_dialog_statuses(campaign_id)
    
    for dialog in data.get('dialogs', []):
        try:
            session_name = dialog.get('session_name')
            user_id = dialog.get('user_id')
            username = dialog.get('username')
            messages = dialog.get('messages', [])
            status = dialog.get('status', 'none')
            
            if not session_name or not user_id:
                skipped_count += 1
                continue
            
            # Формируем имя файла
            if username:
                filename = f"{session_name}_{user_id}_{username}.jsonl"
            else:
                filename = f"{session_name}_{user_id}.jsonl"
            
            filepath = os.path.join(convos_dir, filename)
            
            # Записываем сообщения
            with open(filepath, 'w', encoding='utf-8') as f:
                for msg in messages:
                    f.write(json.dumps({
                        'role': msg.get('role', 'user'),
                        'content': msg.get('content', '')
                    }, ensure_ascii=False) + '\n')
            
            # Сохраняем статус
            dialog_key = f"{session_name}_{user_id}"
            if status and status != 'none':
                statuses[dialog_key] = status
            
            imported_count += 1
            
        except Exception as e:
            print(f"Error importing dialog: {e}")
            skipped_count += 1
    
    # Сохраняем статусы
    _save_dialog_statuses(campaign_id, statuses)
    
    return {
        "status": "imported",
        "imported_count": imported_count,
        "skipped_count": skipped_count
    }


# ============================================================
# Общие роуты для диалогов (ПОСЛЕ специфичных роутов!)
# ============================================================

@router.get("/{campaign_id}", response_model=List[Dialog])
async def get_campaign_dialogs(campaign_id: str):
    """Получить все диалоги кампании (отсортированные по времени последнего сообщения)"""
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
    
    # Загружаем статусы диалогов (используем campaign_id для надёжности)
    statuses = _load_dialog_statuses(campaign_id)
    
    # Читаем все файлы диалогов
    for filename in os.listdir(convos_dir):
        if filename.endswith('.jsonl'):
            try:
                # Парсим имя файла: sessionname_userid_username.jsonl
                # ВАЖНО: split с maxsplit=2, т.к. username может содержать _
                parts = filename.replace('.jsonl', '').split('_', 2)
                
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
                    
                    # Получаем время последней модификации файла
                    last_message_time = _get_file_modification_time(filepath)
                    
                    # Получаем статус диалога
                    dialog_key = _get_dialog_key(session_name, user_id)
                    status_str = statuses.get(dialog_key, "none")
                    try:
                        status = DialogStatus(status_str)
                    except:
                        status = DialogStatus.NONE
                    
                    dialogs.append(Dialog(
                        session_name=session_name,
                        user_id=user_id,
                        username=username,
                        messages=messages,
                        last_message_time=last_message_time,
                        status=status
                    ))
            except Exception as e:
                print(f"Error reading dialog {filename}: {e}")
                continue
    
    # Сортируем по времени последнего сообщения (новые первые)
    dialogs.sort(key=lambda d: d.last_message_time or datetime.min, reverse=True)
    
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
    # ВАЖНО: split с maxsplit=2, т.к. username может содержать _
    filename = possible_files[0].replace('.jsonl', '')
    parts = filename.split('_', 2)
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


# ============================================================
# Отправка сообщений из UI
# ============================================================

def _parse_proxy_url(url: str):
    """Парсит прокси URL для Telethon"""
    if not url or not SOCKS_AVAILABLE:
        return None
    
    try:
        u = urlparse(url)
        proxy_type = u.scheme.upper()
        
        if proxy_type == 'HTTP':
            ptype = ProxyType.HTTP
        elif proxy_type == 'SOCKS5':
            ptype = ProxyType.SOCKS5
        elif proxy_type == 'SOCKS4':
            ptype = ProxyType.SOCKS4
        else:
            return None
        
        proxy_dict = {
            'proxy_type': ptype,
            'addr': u.hostname,
            'port': u.port,
            'rdns': True
        }
        
        if u.username and u.password:
            proxy_dict['username'] = u.username
            proxy_dict['password'] = u.password
        
        return proxy_dict
    except Exception:
        return None


@router.post("/{campaign_id}/send/{session_name}/{user_id}")
async def send_message_to_user(
    campaign_id: str, 
    session_name: str, 
    user_id: int,
    data: SendMessageRequest
):
    """
    Отправить сообщение пользователю из интерфейса.
    Создаёт временное подключение через Telethon.
    """
    if not TELETHON_AVAILABLE:
        raise HTTPException(
            status_code=500, 
            detail="Telethon not available. Install with: pip install telethon"
        )
    
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Ищем аккаунт
    account = None
    for acc in campaign.accounts:
        if acc.session_name == session_name:
            account = acc
            break
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {session_name} not found")
    
    # Путь к сессии
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    sessions_dir = os.path.join(project_root, "data", "sessions")
    session_path = os.path.join(sessions_dir, session_name)
    
    if not os.path.exists(session_path + ".session"):
        raise HTTPException(status_code=404, detail=f"Session file not found for {session_name}")
    
    # Настраиваем прокси
    proxy_dict = None
    if account.proxy_id:
        for proxy in campaign.proxies:
            if proxy.id == account.proxy_id:
                proxy_dict = _parse_proxy_url(proxy.url)
                break
    
    # Создаём клиент и отправляем сообщение
    client = None
    try:
        client = TelegramClient(
            session_path,
            account.api_id,
            account.api_hash,
            proxy=proxy_dict,
            connection_retries=1,
            timeout=15
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Account not authorized")
        
        # Отправляем сообщение по user_id
        await client.send_message(user_id, data.message)
        
        # Сохраняем в историю диалога
        work_folder = campaign.work_folder
        if not os.path.isabs(work_folder):
            work_folder = os.path.join(project_root, work_folder)
        
        convos_dir = os.path.join(work_folder, "convos")
        
        # Ищем файл диалога
        dialog_file = None
        if os.path.exists(convos_dir):
            for filename in os.listdir(convos_dir):
                if filename.startswith(f"{session_name}_{user_id}") and filename.endswith('.jsonl'):
                    dialog_file = os.path.join(convos_dir, filename)
                    break
        
        if dialog_file:
            # Добавляем сообщение в историю
            with open(dialog_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    "role": "assistant",
                    "content": data.message
                }, ensure_ascii=False) + "\n")
        
        return {"status": "sent", "message": "Message sent successfully"}
    
    except RPCError as e:
        raise HTTPException(status_code=400, detail=f"Telegram error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    finally:
        if client:
            try:
                await client.disconnect()
            except:
                pass