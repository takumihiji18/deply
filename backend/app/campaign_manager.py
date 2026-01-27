import asyncio
import os
import sys
import json
import shutil
import time
from typing import Dict, Optional, List
from datetime import datetime
import subprocess
import threading
import platform

from .models import Campaign, CampaignStatus, Account
from .database import db


class CampaignRunner:
    """Менеджер для запуска и управления кампаниями"""
    
    def __init__(self):
        self.running_campaigns: Dict[str, subprocess.Popen] = {}
        self.campaign_logs: Dict[str, List[str]] = {}
    
    async def start_campaign(self, campaign_id: str) -> bool:
        """Запустить кампанию"""
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            return False
        
        if campaign_id in self.running_campaigns:
            return False  # Already running
        
        # Создать конфиг для кампании
        config_path = await self._create_campaign_config(campaign)
        if not config_path:
            return False
        
        # Обновить статус
        campaign.status = CampaignStatus.RUNNING
        await db.save_campaign(campaign)
        
        try:
            # Определить путь к корню проекта
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            
            # Копировать main.py в папку кампании (в КОРНЕ проекта)
            campaign_dir = os.path.join(project_root, "campaigns_runtime", campaign_id)
            
            main_py_src = os.path.join(project_root, "main.py")
            main_py_dst = os.path.join(campaign_dir, "main.py")
            
            if os.path.exists(main_py_src):
                shutil.copy2(main_py_src, main_py_dst)
                print(f"✓ Copied main.py from {main_py_src} to {main_py_dst}")
            else:
                error_msg = (
                    f"Error: main.py not found at {main_py_src}\n"
                    f"Project root: {project_root}\n"
                    f"Backend dir: {backend_dir}\n"
                    f"Current dir: {os.getcwd()}\n"
                    f"Please ensure main.py exists in the project root."
                )
                print(error_msg)
                
                if campaign_id not in self.campaign_logs:
                    self.campaign_logs[campaign_id] = []
                self.campaign_logs[campaign_id].append(f"[ERROR] {error_msg}")
                
                campaign.status = CampaignStatus.ERROR
                await db.save_campaign(campaign)
                return False
            
            # ============================================================
            # ВАЖНО: Финальная проверка перед запуском процесса
            # ============================================================
            import time
            
            # Проверяем наличие критичных файлов
            api_map_path = os.path.join(campaign_dir, "api_map.txt")
            sessions_dir = os.path.join(campaign_dir, "data", "sessions")
            
            # Ждём пока файлы появятся (максимум 3 секунды)
            for attempt in range(6):
                api_map_exists = os.path.exists(api_map_path) and os.path.getsize(api_map_path) > 0
                sessions_exist = os.path.exists(sessions_dir) and len([f for f in os.listdir(sessions_dir) if f.endswith('.session')]) > 0
                
                if api_map_exists and sessions_exist:
                    print(f"✓ Pre-launch verification passed (attempt {attempt + 1})")
                    break
                else:
                    print(f"⏳ Waiting for files... (attempt {attempt + 1}/6)")
                    print(f"   api_map.txt: {'exists' if api_map_exists else 'MISSING'}")
                    print(f"   sessions: {'found' if sessions_exist else 'MISSING'}")
                    time.sleep(0.5)
            else:
                # После всех попыток всё равно логируем состояние
                print(f"⚠ Pre-launch verification: files may not be ready")
                print(f"   api_map.txt exists: {os.path.exists(api_map_path)}")
                print(f"   sessions_dir exists: {os.path.exists(sessions_dir)}")
                if os.path.exists(sessions_dir):
                    print(f"   sessions_dir contents: {os.listdir(sessions_dir)}")
            
            # Запустить процесс с main.py
            # На Windows используем subprocess.Popen
            # Важно: используем -u для unbuffered output чтобы логи сразу попадали в stdout
            env = {
                **os.environ, 
                "CONFIG_PATH": config_path,
                "PYTHONUNBUFFERED": "1"  # Отключить буферизацию
            }
            
            if platform.system() == 'Windows':
                # Windows: используем стандартный subprocess
                process = subprocess.Popen(
                    [sys.executable, "-u", "main.py"],  # -u для unbuffered
                    cwd=campaign_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                    bufsize=0,  # Без буферизации!
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            else:
                # Linux/Mac: используем asyncio
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-u",  # -u для unbuffered
                    "main.py",
                    cwd=campaign_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env
                )
            
            self.running_campaigns[campaign_id] = process
            self.campaign_logs[campaign_id] = [
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Кампания запущена",
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID: {process.pid}",
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Config: {config_path}",
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Platform: {platform.system()}",
                "=" * 80
            ]
            
            # Запустить чтение логов в фоне
            if platform.system() == 'Windows':
                # Windows: читаем в отдельном потоке
                thread = threading.Thread(
                    target=self._read_logs_sync,
                    args=(campaign_id, process),
                    daemon=True
                )
                thread.start()
            else:
                # Linux/Mac: используем asyncio
                asyncio.create_task(self._read_logs(campaign_id, process))
            
            return True
        except Exception as e:
            import traceback
            error_msg = f"Error starting campaign {campaign_id}: {e}\n{traceback.format_exc()}"
            print(error_msg)
            
            if campaign_id not in self.campaign_logs:
                self.campaign_logs[campaign_id] = []
            self.campaign_logs[campaign_id].append(f"[ERROR] {error_msg}")
            
            campaign.status = CampaignStatus.ERROR
            await db.save_campaign(campaign)
            return False
    
    async def stop_campaign(self, campaign_id: str) -> bool:
        """
        Остановить кампанию.
        
        Возвращает True если:
        - Процесс был успешно остановлен
        - Процесс не был запущен (статус просто сбрасывается)
        
        Возвращает False только если кампания не найдена в БД.
        """
        campaign = await db.get_campaign(campaign_id)
        if not campaign:
            return False
        
        # Если процесс не запущен - просто обновляем статус
        if campaign_id not in self.running_campaigns:
            campaign.status = CampaignStatus.STOPPED
            await db.save_campaign(campaign)
            
            # Добавляем сообщение в логи
            if campaign_id in self.campaign_logs:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.campaign_logs[campaign_id].append(
                    f"[{timestamp}] Кампания остановлена (процесс не был запущен)"
                )
            
            return True
        
        try:
            process = self.running_campaigns[campaign_id]
            
            # Пытаемся мягко завершить процесс
            try:
                process.terminate()
            except Exception as e:
                print(f"Warning: terminate failed: {e}")
            
            # Ждем завершения процесса
            if platform.system() == 'Windows':
                # Windows: subprocess.Popen
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print(f"Process {campaign_id} did not terminate in time, killing...")
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception as e:
                        print(f"Warning: kill failed: {e}")
                except Exception as e:
                    print(f"Warning: wait failed: {e}")
            else:
                # Linux/Mac: asyncio process
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    print(f"Process {campaign_id} did not terminate in time, killing...")
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except Exception as e:
                        print(f"Warning: kill failed: {e}")
                except Exception as e:
                    print(f"Warning: wait failed: {e}")
            
            # Удаляем из списка запущенных (даже если что-то пошло не так)
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # Обновляем статус в БД
            campaign.status = CampaignStatus.STOPPED
            await db.save_campaign(campaign)
            
            # Добавляем сообщение в логи
            if campaign_id in self.campaign_logs:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.campaign_logs[campaign_id].append(
                    f"[{timestamp}] Кампания остановлена пользователем"
                )
            
            return True
            
        except Exception as e:
            import traceback
            print(f"Error stopping campaign {campaign_id}: {e}\n{traceback.format_exc()}")
            
            # Даже при ошибке пытаемся обновить статус
            try:
                if campaign_id in self.running_campaigns:
                    del self.running_campaigns[campaign_id]
                campaign.status = CampaignStatus.STOPPED
                await db.save_campaign(campaign)
            except Exception:
                pass
            
            return True  # Возвращаем True - кампания больше не "running"
    
    async def get_campaign_logs(self, campaign_id: str, limit: int = 100) -> List[str]:
        """Получить логи кампании"""
        logs = self.campaign_logs.get(campaign_id, [])
        return logs[-limit:]
    
    def is_running(self, campaign_id: str) -> bool:
        """Проверить, запущена ли кампания"""
        return campaign_id in self.running_campaigns
    
    def _update_campaign_status_sync(self, campaign_id: str, exit_code: int):
        """
        Обновить статус кампании в БД (синхронная версия для использования из потока).
        exit_code: 0 = нормальное завершение, другой = ошибка
        """
        try:
            # Создаём новый event loop для синхронного контекста
            import asyncio
            
            async def update_status():
                campaign = await db.get_campaign(campaign_id)
                if campaign:
                    if exit_code == 0:
                        campaign.status = CampaignStatus.STOPPED
                        msg = f"Кампания {campaign_id} остановлена (код выхода: 0)"
                    else:
                        campaign.status = CampaignStatus.ERROR
                        msg = f"Кампания {campaign_id} завершилась с ошибкой (код выхода: {exit_code})"
                    
                    await db.save_campaign(campaign)
                    print(f"[STATUS UPDATE] {msg}")
                    
                    # Добавляем сообщение в логи
                    if campaign_id in self.campaign_logs:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.campaign_logs[campaign_id].append(f"[{timestamp}] {msg}")
            
            # Пытаемся получить текущий event loop
            try:
                loop = asyncio.get_running_loop()
                # Если мы в асинхронном контексте, создаём задачу
                asyncio.run_coroutine_threadsafe(update_status(), loop)
            except RuntimeError:
                # Нет текущего loop, создаём новый
                asyncio.run(update_status())
                
        except Exception as e:
            print(f"[ERROR] Failed to update campaign status: {e}")
    
    async def _create_campaign_config(self, campaign: Campaign) -> Optional[str]:
        """Создать config.json для кампании"""
        try:
            # Определить корень проекта (на уровень выше backend/)
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            
            # Создать папку для кампании в корне проекта
            campaign_dir = os.path.join(project_root, "campaigns_runtime", campaign.id)
            os.makedirs(campaign_dir, exist_ok=True)
            
            # Создать work folder
            work_folder = os.path.join(campaign_dir, "data")
            os.makedirs(work_folder, exist_ok=True)
            
            # Создать папку для сессий
            sessions_dir = os.path.join(work_folder, "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            
            # ОЧИСТКА СТАРЫХ ФАЙЛОВ (важно для корректного удаления аккаунтов)
            print(f"\n{'='*80}")
            print(f"CLEANING OLD FILES FOR: {campaign.id}")
            print(f"{'='*80}")
            
            # Удаляем старые .session файлы
            if os.path.exists(sessions_dir):
                for file in os.listdir(sessions_dir):
                    if file.endswith('.session'):
                        old_session = os.path.join(sessions_dir, file)
                        os.remove(old_session)
                        print(f"  🗑 Удалён старый файл: {file}")
            
            # Удаляем старые .json файлы аккаунтов
            campaign_data_dir = os.path.join(campaign_dir, "data")
            if os.path.exists(campaign_data_dir):
                for file in os.listdir(campaign_data_dir):
                    if file.endswith('.json'):
                        old_json = os.path.join(campaign_data_dir, file)
                        os.remove(old_json)
                        print(f"  🗑 Удалён старый JSON: {file}")
            
            # Удаляем старый api_map.txt
            old_api_map = os.path.join(campaign_dir, "api_map.txt")
            if os.path.exists(old_api_map):
                os.remove(old_api_map)
                print(f"  🗑 Удалён старый api_map.txt")
            
            print(f"✓ Очистка завершена\n")
            
            # Копировать сессии аккаунтов и подготовить api_map.txt + proxies.txt
            print(f"{'='*80}")
            print(f"CREATING CAMPAIGN CONFIG FOR: {campaign.id}")
            print(f"Campaign name: {campaign.name}")
            print(f"Total accounts: {len(campaign.accounts)}")
            print(f"Active accounts: {len([a for a in campaign.accounts if a.is_active])}")
            print(f"{'='*80}\n")
            
            api_map_lines = []
            account_configs = {}  # Хранить конфиг для каждого аккаунта (включая прокси)
            
            for account in campaign.accounts:
                print(f"\n--- Processing account: {account.session_name} ---")
                print(f"  is_active: {account.is_active}")
                print(f"  api_id: {account.api_id}")
                print(f"  api_hash: {account.api_hash[:10] if account.api_hash else 'EMPTY'}...")
                print(f"  proxy_id: {account.proxy_id if account.proxy_id else 'none'}")
                
                if not account.is_active:
                    print(f"  ⏭ SKIPPED (not active)")
                    continue
                
                # Копировать .session файл (из корня проекта)
                src_session = os.path.join(project_root, "data", "sessions", f"{account.session_name}.session")
                dst_session = os.path.join(sessions_dir, f"{account.session_name}.session")
                
                print(f"  Source: {src_session}")
                print(f"  Dest: {dst_session}")
                print(f"  Source exists: {os.path.exists(src_session)}")
                
                if os.path.exists(src_session):
                    shutil.copy2(src_session, dst_session)
                    file_size = os.path.getsize(dst_session)
                    print(f"  ✓✓✓ Скопирован {account.session_name}.session ({file_size} байт)")
                    
                    # Автоматически конвертировать старые сессии в новый формат
                    self._auto_fix_session(dst_session.replace('.session', ''))
                else:
                    print(f"  ✗✗✗ ОШИБКА: Файл не найден {src_session}")
                    print(f"  ✗✗✗ Проверьте что файл загружен через веб-интерфейс!")
                    continue
                
                # Добавить в api_map.txt (формат: session_name api_id api_hash)
                api_map_lines.append(f"{account.session_name} {account.api_id} {account.api_hash}")
                print(f"  ✓ Добавлен в api_map.txt")
                
                # Найти прокси по proxy_id из campaign.proxies
                proxy_url = None
                if account.proxy_id:
                    for proxy in campaign.proxies:
                        if proxy.id == account.proxy_id:
                            proxy_url = proxy.url
                            print(f"  ✓ Найден прокси для аккаунта: {proxy_url[:50]}...")
                            break
                    if not proxy_url:
                        print(f"  ⚠ Прокси с ID {account.proxy_id} не найден в списке!")
                
                # Создать JSON файл для аккаунта с прокси
                account_json = {
                    "api_id": account.api_id,
                    "api_hash": account.api_hash,
                    "phone": account.phone
                }
                if proxy_url:
                    account_json["proxy"] = proxy_url
                    print(f"  ✓ Прокси добавлен в JSON: {proxy_url[:50]}...")
                
                account_configs[account.session_name] = account_json
            
            # Записать api_map.txt
            if api_map_lines:
                api_map_path = os.path.join(campaign_dir, "api_map.txt")
                with open(api_map_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(api_map_lines))
                    f.flush()  # Принудительный flush в буфер ОС
                    os.fsync(f.fileno())  # Принудительная запись на диск
                print(f"✓ Создан api_map.txt с {len(api_map_lines)} аккаунтами")
                print(f"  Содержимое api_map.txt:")
                for line in api_map_lines:
                    parts = line.split()
                    if len(parts) >= 3:
                        print(f"    {parts[0]}: api_id={parts[1]}, api_hash={parts[2][:10]}...")
            else:
                print(f"⚠ Нет активных аккаунтов для api_map.txt!")
            
            # Создать JSON файлы для каждого аккаунта В CAMPAIGN_DIR/data/
            campaign_data_dir = os.path.join(campaign_dir, "data")
            os.makedirs(campaign_data_dir, exist_ok=True)
            
            for session_name, config in account_configs.items():
                json_path = os.path.join(campaign_data_dir, f"{session_name}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                proxy_info = config.get('proxy', 'no proxy')[:50] if config.get('proxy') else 'NO PROXY'
                print(f"✓ Создан {session_name}.json с прокси: {proxy_info}")
                print(f"  Путь: {json_path}")
            
            # Создать config.json
            config = {
                "WORK_FOLDER": work_folder,
                "PROCESSED_CLIENTS": os.path.join(campaign_dir, "processed_clients.txt"),
                "PROJECT_NAME": campaign.openai_settings.project_name or campaign.name,
                "OPENAI": {
                    "API_KEY": campaign.openai_settings.api_key,
                    "MODEL": campaign.openai_settings.model,
                    "PROXY": campaign.openai_settings.proxy or None,
                    "SYSTEM_TXT": os.path.join(campaign_dir, "prompt.txt"),
                    "TRIGGER_PHRASES": {
                        "POSITIVE": campaign.openai_settings.trigger_phrases_positive,
                        "NEGATIVE": campaign.openai_settings.trigger_phrases_negative
                    },
                    "TARGET_CHATS": {
                        "POSITIVE": campaign.openai_settings.target_chats_positive,
                        "NEGATIVE": campaign.openai_settings.target_chats_negative
                    },
                    "USE_FALLBACK_ON_OPENAI_FAIL": campaign.openai_settings.use_fallback_on_fail,
                    "FALLBACK_TEXT": campaign.openai_settings.fallback_text
                },
                "TELEGRAM_FORWARD_LIMIT": campaign.telegram_settings.forward_limit,
                "REPLY_ONLY_IF_PREVIOUSLY_WROTE": campaign.telegram_settings.reply_only_if_previously_wrote,
                "TELEGRAM_HISTORY_LIMIT": campaign.telegram_settings.history_limit,
                "PRE_READ_DELAY_RANGE": campaign.telegram_settings.pre_read_delay_range,
                "READ_REPLY_DELAY_RANGE": campaign.telegram_settings.read_reply_delay_range,
                "ACCOUNT_LOOP_DELAY_RANGE": campaign.telegram_settings.account_loop_delay_range,
                "DIALOG_WAIT_WINDOW_RANGE": campaign.telegram_settings.dialog_wait_window_range,
                "SLEEP_PERIODS": campaign.telegram_settings.sleep_periods,
                "TIMEZONE_OFFSET": campaign.telegram_settings.timezone_offset,
                # Фильтр ботов (не отвечать на юзернеймы начинающиеся на i7/i8)
                "IGNORE_BOT_USERNAMES": campaign.telegram_settings.ignore_bot_usernames if hasattr(campaign.telegram_settings, 'ignore_bot_usernames') else True,
                # Не отвечать пользователям без юзернейма
                "IGNORE_NO_USERNAME": campaign.telegram_settings.ignore_no_username if hasattr(campaign.telegram_settings, 'ignore_no_username') else True,
                # Время отлёжки аккаунта при Peer Flood
                "ACCOUNT_COOLDOWN_HOURS": campaign.telegram_settings.account_cooldown_hours if hasattr(campaign.telegram_settings, 'account_cooldown_hours') else 5,
                # Follow-up настройки
                "FOLLOW_UP": {
                    "enabled": campaign.telegram_settings.follow_up.enabled if campaign.telegram_settings.follow_up else False,
                    "delay_hours": campaign.telegram_settings.follow_up.delay_hours if campaign.telegram_settings.follow_up else 24,
                    "prompt": campaign.telegram_settings.follow_up.prompt if campaign.telegram_settings.follow_up else "Напиши короткое напоминание о себе. Вежливо напомни о предложении и спроси, актуально ли оно ещё. Если не актуально - попроси сообщить об этом. Сообщение должно быть кратким (2-3 предложения)."
                }
            }
            
            config_path = os.path.join(campaign_dir, "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Создать prompt.txt
            prompt_path = os.path.join(campaign_dir, "prompt.txt")
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(campaign.openai_settings.system_prompt)
                f.flush()
                os.fsync(f.fileno())
            
            # Создать processed_clients.txt с дефолтными ботами
            processed_path = os.path.join(campaign_dir, "processed_clients.txt")
            if not os.path.exists(processed_path):
                with open(processed_path, 'w', encoding='utf-8') as f:
                    f.write("178220800 | SpamBot\n")
                    f.write("5314653481 | PremiumBot\n")
            
            # ============================================================
            # ВАЖНО: Верификация созданных файлов
            # Иногда файловая система не успевает синхронизироваться
            # ============================================================
            print(f"\n{'='*80}")
            print("VERIFYING CREATED FILES...")
            print(f"{'='*80}")
            
            # Принудительная синхронизация файловой системы
            try:
                import time
                time.sleep(0.5)  # Небольшая задержка для sync
                
                # Проверяем критичные файлы
                files_to_verify = [
                    ("config.json", config_path),
                    ("api_map.txt", os.path.join(campaign_dir, "api_map.txt")),
                    ("prompt.txt", prompt_path),
                ]
                
                # Добавляем сессии для проверки
                for session_name in account_configs.keys():
                    session_file = os.path.join(sessions_dir, f"{session_name}.session")
                    files_to_verify.append((f"{session_name}.session", session_file))
                    json_file = os.path.join(campaign_data_dir, f"{session_name}.json")
                    files_to_verify.append((f"{session_name}.json", json_file))
                
                all_ok = True
                for name, path in files_to_verify:
                    exists = os.path.exists(path)
                    size = os.path.getsize(path) if exists else 0
                    status = f"✓ OK ({size} bytes)" if exists and size > 0 else "✗ MISSING/EMPTY"
                    print(f"  {name}: {status}")
                    if not exists or size == 0:
                        all_ok = False
                
                if not all_ok:
                    print(f"\n⚠ WARNING: Some files are missing or empty!")
                    print(f"Waiting additional 1 second for filesystem sync...")
                    time.sleep(1.0)
                    
                    # Повторная проверка
                    for name, path in files_to_verify:
                        if not os.path.exists(path) or os.path.getsize(path) == 0:
                            print(f"  STILL MISSING: {name}")
                
                print(f"✓ File verification completed\n")
                
            except Exception as verify_err:
                print(f"⚠ Verification warning: {verify_err}")
            
            return config_path
        except Exception as e:
            print(f"Error creating config for campaign {campaign.id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _auto_fix_session(self, session_path: str) -> bool:
        """
        Автоматически исправляет файл сессии если он в старом формате (6 столбцов)
        Конвертирует в новый формат (5 столбцов) для совместимости с Python 3.13+
        """
        import sqlite3
        
        session_file = session_path + ".session"
        
        if not os.path.exists(session_file):
            return True
        
        conn = None
        try:
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            
            # Проверяем количество столбцов в таблице sessions
            cursor.execute("PRAGMA table_info(sessions)")
            columns = cursor.fetchall()
            
            if len(columns) == 6:
                print(f"Auto-fixing session format: {os.path.basename(session_file)}")
                
                # Создаем backup
                backup_file = session_file + ".backup"
                if not os.path.exists(backup_file):
                    shutil.copy2(session_file, backup_file)
                
                # Читаем данные
                cursor.execute("SELECT * FROM sessions")
                row = cursor.fetchone()
                
                if row and len(row) == 6:
                    # Переименовываем старую таблицу
                    cursor.execute("ALTER TABLE sessions RENAME TO sessions_old")
                    
                    # Создаем новую таблицу с 5 столбцами
                    cursor.execute("""
                        CREATE TABLE sessions (
                            dc_id INTEGER PRIMARY KEY,
                            server_address TEXT,
                            port INTEGER,
                            auth_key BLOB,
                            takeout_id INTEGER
                        )
                    """)
                    
                    # Копируем данные (первые 5 столбцов)
                    cursor.execute("""
                        INSERT INTO sessions (dc_id, server_address, port, auth_key, takeout_id)
                        SELECT dc_id, server_address, port, auth_key, takeout_id
                        FROM sessions_old
                    """)
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE sessions_old")
                    
                    conn.commit()
                    print(f"Session fixed successfully: {os.path.basename(session_file)}")
            
            return True
            
        except Exception as e:
            print(f"Failed to check/fix session {session_file}: {e}")
            return False
        finally:
            # ВАЖНО: Всегда закрываем соединение чтобы избежать утечки ресурсов
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _read_logs_sync(self, campaign_id: str, process: subprocess.Popen):
        """Читать логи из процесса (синхронная версия для Windows)"""
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                log_line = line.strip()
                if not log_line:
                    continue
                
                # Добавляем timestamp если его нет
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if not log_line.startswith('['):
                    log_line = f"[{timestamp}] {log_line}"
                
                if campaign_id not in self.campaign_logs:
                    self.campaign_logs[campaign_id] = []
                
                self.campaign_logs[campaign_id].append(log_line)
                print(log_line)  # Также выводим в консоль
                
                # Ограничить размер логов
                if len(self.campaign_logs[campaign_id]) > 1000:
                    self.campaign_logs[campaign_id] = self.campaign_logs[campaign_id][-1000:]
            
            # Процесс завершился
            exit_code = process.wait()
            final_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Процесс завершен с кодом {exit_code}"
            if campaign_id in self.campaign_logs:
                self.campaign_logs[campaign_id].append(final_msg)
            print(final_msg)
            
            # Удалить из running_campaigns
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # ВАЖНО: Обновляем статус кампании в БД
            # Используем asyncio для вызова асинхронной функции из синхронного контекста
            self._update_campaign_status_sync(campaign_id, exit_code)
            
        except Exception as e:
            import traceback
            error_msg = f"Error reading logs for {campaign_id}: {e}\n{traceback.format_exc()}"
            print(error_msg)
            if campaign_id in self.campaign_logs:
                self.campaign_logs[campaign_id].append(f"[ERROR] {error_msg}")
            
            # Удалить из running_campaigns при ошибке
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # Обновляем статус на ERROR
            self._update_campaign_status_sync(campaign_id, -1)
    
    async def _read_logs(self, campaign_id: str, process: asyncio.subprocess.Process):
        """Читать логи из процесса (асинхронная версия для Linux/Mac)"""
        exit_code = -1
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                log_line = line.decode('utf-8', errors='replace').strip()
                if not log_line:
                    continue
                
                # Добавляем timestamp если его нет
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if not log_line.startswith('['):
                    log_line = f"[{timestamp}] {log_line}"
                
                if campaign_id not in self.campaign_logs:
                    self.campaign_logs[campaign_id] = []
                
                self.campaign_logs[campaign_id].append(log_line)
                print(log_line)  # Также выводим в консоль
                
                # Ограничить размер логов
                if len(self.campaign_logs[campaign_id]) > 1000:
                    self.campaign_logs[campaign_id] = self.campaign_logs[campaign_id][-1000:]
            
            # Процесс завершился
            exit_code = await process.wait()
            final_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Процесс завершен с кодом {exit_code}"
            if campaign_id in self.campaign_logs:
                self.campaign_logs[campaign_id].append(final_msg)
            print(final_msg)
            
            # Удалить из running_campaigns
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # ВАЖНО: Обновляем статус кампании в БД
            await self._update_campaign_status_async(campaign_id, exit_code)
            
        except Exception as e:
            import traceback
            error_msg = f"Error reading logs for {campaign_id}: {e}\n{traceback.format_exc()}"
            print(error_msg)
            if campaign_id in self.campaign_logs:
                self.campaign_logs[campaign_id].append(f"[ERROR] {error_msg}")
            
            # Удалить из running_campaigns при ошибке
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # Обновляем статус на ERROR
            await self._update_campaign_status_async(campaign_id, -1)
    
    async def _update_campaign_status_async(self, campaign_id: str, exit_code: int):
        """
        Обновить статус кампании в БД (асинхронная версия).
        exit_code: 0 = нормальное завершение, другой = ошибка
        """
        try:
            campaign = await db.get_campaign(campaign_id)
            if campaign:
                if exit_code == 0:
                    campaign.status = CampaignStatus.STOPPED
                    msg = f"Кампания {campaign_id} остановлена (код выхода: 0)"
                else:
                    campaign.status = CampaignStatus.ERROR
                    msg = f"Кампания {campaign_id} завершилась с ошибкой (код выхода: {exit_code})"
                
                await db.save_campaign(campaign)
                print(f"[STATUS UPDATE] {msg}")
                
                # Добавляем сообщение в логи
                if campaign_id in self.campaign_logs:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.campaign_logs[campaign_id].append(f"[{timestamp}] {msg}")
        except Exception as e:
            print(f"[ERROR] Failed to update campaign status: {e}")


# Singleton instance
campaign_runner = CampaignRunner()

