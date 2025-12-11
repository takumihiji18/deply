import asyncio
import json
import os
import random
import datetime
import sqlite3
import shutil
import sys
from urllib.parse import urlparse
from typing import Optional

import aiohttp
from telethon import TelegramClient
from telethon.tl.types import Message, User, Dialog, PeerUser
from telethon.errors import (
    SessionPasswordNeededError,
    UnauthorizedError,
    FloodWaitError,
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    PhoneNumberBannedError,
    RPCError
)
from telethon import functions

# Импорт для работы с прокси
try:
    import python_socks
    from python_socks import ProxyType
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    ProxyType = None
    print("Warning: python-socks not available. Proxy support disabled.")

# ======================== CONFIG ========================
print("="*80)
print("MAIN.PY STARTED")
print(f"Current directory: {os.getcwd()}")
print(f"Config file exists: {os.path.exists('config.json')}")
print("="*80)

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

WORK_FOLDER = CONFIG["WORK_FOLDER"]
PROCESSED_FILE = CONFIG["PROCESSED_CLIENTS"]
OPENAI_CFG = CONFIG["OPENAI"]
FORWARD_LIMIT = CONFIG.get("TELEGRAM_FORWARD_LIMIT", 5)
REPLY_ONLY_IF_PREV = CONFIG.get("REPLY_ONLY_IF_PREVIOUSLY_WROTE", True)
PROJECT_NAME = CONFIG.get("PROJECT_NAME", "")
TELEGRAM_HISTORY_LIMIT = CONFIG.get("TELEGRAM_HISTORY_LIMIT", 100)
PRE_READ_DELAY_RANGE = CONFIG.get("PRE_READ_DELAY_RANGE", [0, 0])
READ_REPLY_DELAY_RANGE = CONFIG.get("READ_REPLY_DELAY_RANGE", [0, 0])
ACCOUNT_LOOP_DELAY_RANGE = CONFIG.get("ACCOUNT_LOOP_DELAY_RANGE", [60, 60])
CHECK_NEW_MSG_INTERVAL_RANGE = CONFIG.get("CHECK_NEW_MSG_INTERVAL_RANGE", [5, 5])
DIALOG_WAIT_WINDOW_RANGE = CONFIG.get("DIALOG_WAIT_WINDOW_RANGE", [30, 30])
SLEEP_PERIODS_RAW = CONFIG.get("SLEEP_PERIODS", [])
# Поддержка разных форматов:
# 1. Строка: "21:00-08:00,13:00-14:00"
# 2. Массив строк: ["21:00-08:00", "13:00-14:00"]  
# 3. Массив с одной строкой: ["21:00-08:00, 13:00-14:00"]
if isinstance(SLEEP_PERIODS_RAW, str):
    # Строка - разбиваем по запятой
    SLEEP_PERIODS = [p.strip() for p in SLEEP_PERIODS_RAW.split(",") if p.strip()]
elif isinstance(SLEEP_PERIODS_RAW, list):
    # Массив - обрабатываем каждый элемент
    SLEEP_PERIODS = []
    for item in SLEEP_PERIODS_RAW:
        if isinstance(item, str):
            # Если элемент массива содержит запятую, разбиваем его
            if "," in item:
                SLEEP_PERIODS.extend([p.strip() for p in item.split(",") if p.strip()])
            else:
                SLEEP_PERIODS.append(item.strip())
else:
    SLEEP_PERIODS = []
TIMEZONE_OFFSET = CONFIG.get("TIMEZONE_OFFSET", 3)  # Часовой пояс (по умолчанию +3 МСК)

os.makedirs(WORK_FOLDER, exist_ok=True)
if not os.path.exists(PROCESSED_FILE):
    open(PROCESSED_FILE, "w").close()

# ======================== LOGGING ========================
def _ts_local() -> str:
    """Возвращает текущее время с учетом часового пояса"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    local_now = utc_now + datetime.timedelta(hours=TIMEZONE_OFFSET)
    return local_now.strftime("%Y-%m-%d %H:%M:%S")

def _get_local_time() -> datetime.datetime:
    """Возвращает текущее datetime с учетом часового пояса"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    return utc_now + datetime.timedelta(hours=TIMEZONE_OFFSET)

def _safe_print(text: str):
    """Безопасный вывод текста в консоль (обработка эмодзи для Windows)"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Windows консоль не поддерживает эмодзи - заменяем на текстовые индикаторы
        text = text.replace('🔍', '[CHECK]')
        text = text.replace('✅', '[OK]')
        text = text.replace('❌', '[FAIL]')
        text = text.replace('🔄', '[RETRY]')
        text = text.replace('⚠️', '[WARN]')
        text = text.replace('🚫', '[BAN]')
        text = text.replace('📱', '[PHONE]')
        text = text.replace('⏭', '[SKIP]')
        print(text)

def log_error(text: str):
    ts = _ts_local()
    line = f"[{ts} MSK] {text}"
    _safe_print(line)
    try:
        with open("errors.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def log_info(msg: str):
    _safe_print(f"[{_ts_local()} MSK] {msg}")

# ======================== SLEEP PERIODS ========================
def parse_sleep_period(period_str: str) -> tuple[datetime.time, datetime.time]:
    """
    Парсит строку периода сна в формате "HH:MM-HH:MM"
    Возвращает (start_time, end_time)
    """
    try:
        # Убираем пробелы с краев
        period_str = period_str.strip()
        start_str, end_str = period_str.split("-")
        start_hour, start_min = map(int, start_str.strip().split(":"))
        end_hour, end_min = map(int, end_str.strip().split(":"))
        return (
            datetime.time(start_hour, start_min),
            datetime.time(end_hour, end_min)
        )
    except Exception as e:
        log_error(f"Failed to parse sleep period '{period_str}': {e}")
        return None

def is_sleep_time() -> bool:
    """
    Проверяет, находимся ли мы в "спящем" времени
    Возвращает True если сейчас время сна, иначе False
    """
    if not SLEEP_PERIODS:
        return False
    
    current_time = _get_local_time().time()
    
    for period_str in SLEEP_PERIODS:
        result = parse_sleep_period(period_str)
        if not result:
            continue
        
        start_time, end_time = result
        
        # Случай когда период переходит через полночь (например 21:00-08:00)
        if start_time > end_time:
            if current_time >= start_time or current_time <= end_time:
                return True
        # Обычный случай (например 13:00-14:00)
        else:
            if start_time <= current_time <= end_time:
                return True
    
    return False

def get_next_wake_time() -> Optional[datetime.datetime]:
    """
    Возвращает время когда программа должна "проснуться"
    (ближайшее время окончания текущего периода сна)
    Возвращает naive datetime в местном времени для упрощения вычислений
    """
    if not SLEEP_PERIODS:
        return None
    
    # Работаем с местным временем без timezone info для упрощения
    current_dt = _get_local_time().replace(tzinfo=None)
    current_time = current_dt.time()
    
    wake_times = []
    
    for period_str in SLEEP_PERIODS:
        result = parse_sleep_period(period_str)
        if not result:
            continue
        
        start_time, end_time = result
        
        # Проверяем, находимся ли мы в этом периоде
        in_period = False
        if start_time > end_time:  # Переход через полночь
            if current_time >= start_time or current_time <= end_time:
                in_period = True
        else:
            if start_time <= current_time <= end_time:
                in_period = True
        
        if in_period:
            # Вычисляем время окончания периода (naive datetime в местном времени)
            wake_dt = datetime.datetime.combine(current_dt.date(), end_time)
            
            # Если end_time меньше current_time и период через полночь, 
            # значит wake_time завтра
            if end_time < current_time and start_time > end_time:
                wake_dt += datetime.timedelta(days=1)
            
            wake_times.append(wake_dt)
    
    if wake_times:
        return min(wake_times)
    
    return None

async def wait_until_wake_time():
    """
    Ждет пока не закончится период сна
    """
    while is_sleep_time():
        wake_time = get_next_wake_time()
        if wake_time:
            # Используем naive datetime для обоих значений
            now = _get_local_time().replace(tzinfo=None)
            sleep_seconds = (wake_time - now).total_seconds()
            
            if sleep_seconds > 0:
                wake_str = wake_time.strftime("%H:%M:%S")
                log_info(f"Sleep mode: waiting until {wake_str} MSK ({sleep_seconds/60:.1f} minutes)")
                
                # Спим порциями по 5 минут для возможности прерывания
                chunk_size = 300  # 5 минут
                while sleep_seconds > 0:
                    sleep_chunk = min(chunk_size, sleep_seconds)
                    await asyncio.sleep(sleep_chunk)
                    sleep_seconds -= sleep_chunk
                    
                    # Проверяем, не вышли ли мы из периода сна
                    if not is_sleep_time():
                        break
        else:
            # Не должно произойти, но на всякий случай
            await asyncio.sleep(60)
    
    log_info("Sleep mode ended, resuming work")

# ======================== DELAY WITH VARIANCE ========================
async def delay_with_variance(base_range: list[float], variance_percent: float = 0.15):
    """
    Создает задержку с разбросом времени для имитации человеческого поведения.
    variance_percent - процент разброса от среднего значения
    Возвращает фактическое время задержки в секундах.
    """
    if not base_range or len(base_range) < 2:
        return 0
    
    min_val, max_val = base_range[0], base_range[1]
    if min_val == max_val == 0:
        return 0
    
    # Базовая задержка
    base_delay = random.uniform(min_val, max_val)
    
    # Добавляем разброс
    variance = base_delay * variance_percent * random.uniform(-1, 1)
    final_delay = max(0, base_delay + variance)
    
    if final_delay > 0:
        await asyncio.sleep(final_delay)
    
    return final_delay

# ======================== PROMPT ========================
def render_system_prompt() -> str:
    path = OPENAI_CFG.get("SYSTEM_TXT", "prompt.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        return (
            txt.replace("{trigger_phrase_positive}", OPENAI_CFG["TRIGGER_PHRASES"]["POSITIVE"])
               .replace("{trigger_phrase_negative}", OPENAI_CFG["TRIGGER_PHRASES"]["NEGATIVE"])
        )
    return ""

SYSTEM_PROMPT = render_system_prompt()

# ======================== GPT CONTEXT ========================
CONVO_DIR = os.path.join(WORK_FOLDER, "convos")
os.makedirs(CONVO_DIR, exist_ok=True)
CONVO_MAX_TURNS = 10

def convo_path(session_name: str, user_id: int, username: str = None) -> str:
    """Возвращает путь к файлу с историей диалога"""
    if username:
        return os.path.join(CONVO_DIR, f"{session_name}_{user_id}_{username}.jsonl")
    return os.path.join(CONVO_DIR, f"{session_name}_{user_id}.jsonl")

def convo_load(session_name: str, user_id: int, username: str = None) -> list[dict]:
    """Загружает историю диалога из файла"""
    # Сначала пробуем с username
    if username:
        path = convo_path(session_name, user_id, username)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f.read().splitlines() if x.strip()]
            return lines[-(CONVO_MAX_TURNS * 2):]
    
    # Если не нашли, пробуем без username (совместимость)
    path = convo_path(session_name, user_id)
    if not os.path.exists(path):
        return []
    
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    return lines[-(CONVO_MAX_TURNS * 2):]

def convo_append(session_name: str, user_id: int, role: str, content: str, username: str = None):
    """Добавляет сообщение в историю диалога"""
    path = convo_path(session_name, user_id, username)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"role": role, "content": content}, ensure_ascii=False) + "\n")


def convo_save_full_history(session_name: str, user_id: int, history: list[dict], username: str = None):
    """
    Сохраняет полную историю диалога в файл.
    Используется для сохранения истории из Telegram при первом контакте.
    
    history: список словарей {"role": "user"|"assistant", "content": "текст"}
    """
    path = convo_path(session_name, user_id, username)
    
    # Проверяем, пустой ли файл (первый контакт)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return  # Файл уже существует и не пустой - не перезаписываем
    
    # Сохраняем всю историю
    with open(path, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    
    log_info(f"Saved full Telegram history ({len(history)} messages) for {session_name}_{user_id}")

# ======================== PROCESSED USERS ========================
def already_processed(uid: int) -> bool:
    try:
        with open(PROCESSED_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                left = line.split("|", 1)[0].strip()
                if left == str(uid):
                    return True
    except FileNotFoundError:
        return False
    return False

async def mark_processed(client: TelegramClient, user: User, uid: int):
    if already_processed(uid):
        return
    
    username = f"@{user.username}" if user and user.username else "(no username)"
    line = f"{uid} | {username}"
    
    try:
        with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        log_info(f"{client.session.filename}: marked processed {line}")
    except Exception as e:
        log_error(f"{client.session.filename}: cannot write processed: {e!r}")

# ======================== OpenAI API ========================
async def openai_generate(messages: list[dict]) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_CFG['API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {"model": OPENAI_CFG["MODEL"], "messages": messages}
    timeout = aiohttp.ClientTimeout(total=60)
    
    proxy_url = OPENAI_CFG.get("PROXY")
    
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                kwargs = {}
                if proxy_url:
                    kwargs["proxy"] = proxy_url
                
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    **kwargs
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"].strip()
                    err = await resp.text()
                    log_error(f"OpenAI HTTP {resp.status}: {err[:200]}")
        except Exception as e:
            log_error(f"OpenAI error: {e!r}")
        
        await delay_with_variance([1.5 * (attempt + 1), 2 * (attempt + 1)], 0.2)
    
    return ""

# ======================== PROXY HELPERS ========================
def parse_proxy_url(url: str | None):
    """Парсит прокси URL и возвращает dict для Telethon с python-socks"""
    if not url:
        return None
    
    if not SOCKS_AVAILABLE:
        log_error(f"Socks module not available. Install with: pip install python-socks[asyncio]")
        return None
    
    try:
        u = urlparse(url)
        
        # Telethon с python-socks использует словарь
        proxy_type = u.scheme.upper()  # HTTP, SOCKS5, SOCKS4
        
        # Определяем тип прокси
        if proxy_type == 'HTTP':
            ptype = ProxyType.HTTP
        elif proxy_type == 'SOCKS5':
            ptype = ProxyType.SOCKS5
        elif proxy_type == 'SOCKS4':
            ptype = ProxyType.SOCKS4
        else:
            log_error(f"Unsupported proxy type: {proxy_type}. Supported: HTTP, SOCKS5, SOCKS4")
            return None
        
        # Формируем словарь для Telethon
        proxy_dict = {
            'proxy_type': ptype,
            'addr': u.hostname,
            'port': u.port,
            'rdns': True
        }
        
        # Добавляем авторизацию если есть
        if u.username and u.password:
            proxy_dict['username'] = u.username
            proxy_dict['password'] = u.password
        
        return proxy_dict
        
    except Exception as e:
        log_error(f"Failed to parse proxy URL {url}: {e!r}")
        return None

async def check_proxy_connection(proxy_dict: dict, timeout: int = 5) -> bool:
    """
    Проверяет подключение к Telegram API через прокси.
    Делает простой HTTP запрос к Telegram для проверки доступности.
    
    ВАЖНО: Одна попытка, быстрый таймаут (5 сек).
    При неудаче - сразу возвращает False без повторов.
    """
    if not proxy_dict:
        return True  # Нет прокси - считаем что подключение есть
    
    addr = proxy_dict.get('addr', 'unknown')
    port = proxy_dict.get('port', 0)
    
    try:
        username = proxy_dict.get('username')
        password = proxy_dict.get('password')
        
        # Формируем proxy URL для aiohttp
        if username and password:
            proxy_url = f"http://{username}:{password}@{addr}:{port}"
        else:
            proxy_url = f"http://{addr}:{port}"
        
        # Проверяем доступность Telegram API
        test_url = "https://api.telegram.org"
        
        # Короткий таймаут, без retry
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout, connect=3)
        ) as session:
            async with session.get(test_url, proxy=proxy_url) as resp:
                return resp.status in [200, 401, 404]  # Любой ответ от сервера = прокси работает
    
    except Exception as e:
        log_error(f"❌ Proxy check FAILED for {addr}:{port}: {e!r}")
        return False

def load_proxies_from_file(path: str = "proxies.txt") -> list[str]:
    if not os.path.exists(path):
        return []
    return [line.strip() for line in open(path, encoding="utf-8") if line.strip()]

# ======================== TELEGRAM HELPERS ========================
async def resolve_target(client: TelegramClient, raw_target) -> int:
    """Резолвит username/link в chat_id"""
    if isinstance(raw_target, int):
        return raw_target
    
    s = str(raw_target).strip()
    if s.startswith("-100"):
        return int(s)
    if s.startswith("https://t.me/"):
        s = s.split("/")[-1]
    
    try:
        entity = await client.get_entity(s)
        return entity.id
    except Exception as e:
        log_error(f"Cannot resolve target {raw_target}: {e!r}")
        raise

async def _collect_new_incoming_since(
    client: TelegramClient, 
    chat_id: int, 
    last_msg_id: int, 
    max_take: int = 50
) -> list[Message]:
    """Собирает новые входящие сообщения после last_msg_id"""
    res: list[Message] = []
    
    try:
        messages = await client.get_messages(chat_id, limit=max_take)
        
        for m in messages:
            if m.id > last_msg_id and not m.out:
                text = (m.text or "").strip()
                if text:
                    res.append(m)
    except Exception as e:
        log_error(f"{client.session.filename}: _collect_new_incoming_since error chat {chat_id}: {e!r}")
    
    res.reverse()
    return res

# ======================== FORWARD + FALLBACK COPY ========================
async def forward_conversation(
    client: TelegramClient,
    uid: int,
    key: str,
    user: Optional[User] = None,
):
    """Пересылает диалог в целевой чат с пометкой"""
    if already_processed(uid):
        return
    
    raw_target = OPENAI_CFG["TARGET_CHATS"][key]
    try:
        chat_id = await resolve_target(client, raw_target)
    except Exception as e:
        log_error(f"{client.session.filename}: cannot resolve {raw_target}: {e!r}")
        return
    
    project_name = CONFIG.get("PROJECT_NAME", "").strip()
    project_part = f' в "{project_name}"' if project_name else ""
    
    username = None
    if user and user.username:
        username = user.username
    
    who = f"@{username}" if username else f"id {uid}"
    
    if key.upper() == "POSITIVE":
        note = f"✅ Пользователь {who} заинтересован{project_part}"
    else:
        note = f"❌ Пользователь {who} отказался{project_part}"
    
    try:
        await client.send_message(chat_id, note)
    except Exception as e:
        log_error(f"{client.session.filename}: cannot send notification to {chat_id}: {e!r}")
    
    # Получаем последние сообщения для пересылки
    msgs = await client.get_messages(uid, limit=FORWARD_LIMIT)
    msgs = list(reversed(msgs))
    
    forwarded = 0
    for m in msgs:
        try:
            await client.forward_messages(chat_id, m)
            forwarded += 1
        except Exception as e:
            log_error(f"{client.session.filename}: forward failed: {e!r}")
    
    # Если не удалось переслать, отправляем текстом
    if forwarded == 0:
        lines = [f"Диалог с {uid} (последние {len(msgs)}):"]
        for m in msgs:
            who_msg = "Он" if not m.out else "Мы"
            body = (m.text or "<non-text>").strip()
            lines.append(f"{who_msg}: {body[:800]}")
        text_dump = "\n".join(lines)
        try:
            await client.send_message(chat_id, text_dump)
        except Exception as e:
            log_error(f"{client.session.filename}: copy to group failed: {e!r}")
    else:
        log_info(f"{client.session.filename}: forwarded {forwarded}/{len(msgs)} msgs to {chat_id}")

# ======================== CORE PROCESSING ========================
async def _has_outgoing_before(client: TelegramClient, uid: int) -> bool:
    """Проверяет, были ли исходящие сообщения в диалоге"""
    try:
        messages = await client.get_messages(uid, limit=TELEGRAM_HISTORY_LIMIT)
        for m in messages:
            if m.out:
                return True
        return False
    except Exception as e:
        log_error(f"{client.session.filename}: _has_outgoing_before failed for {uid}: {e!r}")
        return False

async def _collect_incoming_slice(
    client: TelegramClient, 
    chat_id: int, 
    max_take: int = 50
) -> list[Message]:
    """Собирает срез входящих сообщений"""
    res: list[Message] = []
    
    try:
        messages = await client.get_messages(chat_id, limit=max_take)
        
        for m in messages:
            if not m.out:
                text = (m.text or "").strip()
                if text:
                    res.append(m)
    except Exception as e:
        log_error(f"{client.session.filename}: _collect_incoming_slice error chat {chat_id}: {e!r}")
    
    res.reverse()
    return res


async def _load_telegram_history(
    client: TelegramClient,
    chat_id: int,
    limit: int = None
) -> list[dict]:
    """
    Загружает историю диалога из Telegram для контекста GPT.
    Включает ВСЕ сообщения - и входящие, и исходящие.
    
    Возвращает список в формате GPT messages:
    [{"role": "user"|"assistant", "content": "текст"}, ...]
    """
    if limit is None:
        limit = TELEGRAM_HISTORY_LIMIT
    
    history = []
    
    try:
        messages = await client.get_messages(chat_id, limit=limit)
        
        # Сообщения приходят от новых к старым, разворачиваем
        messages = list(reversed(messages))
        
        for m in messages:
            text = (m.text or "").strip()
            if not text:
                continue
            
            # m.out = True если это наше исходящее сообщение
            role = "assistant" if m.out else "user"
            history.append({
                "role": role,
                "content": text
            })
    
    except Exception as e:
        log_error(f"_load_telegram_history error for chat {chat_id}: {e!r}")
    
    return history

async def _reply_once_for_batch(
    client: TelegramClient, 
    uid: int, 
    batch: list[Message],
    session_name: str,
    username: str = None
) -> bool:
    """
    Обрабатывает батч сообщений и отвечает один раз.
    Возвращает True если пользователь был помечен как processed, иначе False.
    """
    if not batch:
        return False
    
    # Задержка перед чтением (ВАЖНО: имитация человека)
    pre_delay = await delay_with_variance(PRE_READ_DELAY_RANGE, 0.2)
    if pre_delay and pre_delay > 0:
        log_info(f"{session_name}: ⏳ waiting {pre_delay:.1f}s before reading {uid} (human-like behavior)")
    else:
        log_info(f"{session_name}: ⚠️ WARNING: no pre-read delay configured (PRE_READ_DELAY_RANGE={PRE_READ_DELAY_RANGE})")
    
    # Отмечаем как прочитанное
    try:
        await client.send_read_acknowledge(uid, max_id=batch[-1].id)
        log_info(f"{session_name}: ✓ marked messages as read for {uid}")
    except Exception as e:
        log_error(f"{session_name}: failed to mark as read: {e!r}")
    
    # Задержка между чтением и ответом (ВАЖНО: имитация печати)
    reply_delay = await delay_with_variance(READ_REPLY_DELAY_RANGE, 0.2)
    if reply_delay and reply_delay > 0:
        log_info(f"{session_name}: ⏳ read->reply delay {reply_delay:.1f}s for {uid} (simulating typing)")
    else:
        log_info(f"{session_name}: ⚠️ WARNING: no read-reply delay configured (READ_REPLY_DELAY_RANGE={READ_REPLY_DELAY_RANGE})")
    
    # Загружаем историю разговора из Telegram (включая наше первое сообщение!)
    telegram_history = await _load_telegram_history(client, uid)
    
    # Также загружаем локальную историю (на случай если Telegram история неполная)
    local_history = convo_load(session_name, uid, username)
    
    # ВАЖНО: Сохраняем полную историю из Telegram в файл при первом контакте!
    # Это позволит видеть всю историю в веб-интерфейсе
    if telegram_history and not local_history:
        convo_save_full_history(session_name, uid, telegram_history, username)
        log_info(f"{session_name}: ✓ saved full Telegram history to file for {uid}")
    
    # Используем Telegram историю как основную (там есть первое сообщение)
    # Если Telegram история пустая - используем локальную
    if telegram_history:
        history = telegram_history
        log_info(f"{session_name}: loaded {len(history)} messages from Telegram history for context")
    else:
        history = local_history
        log_info(f"{session_name}: using local history ({len(history)} messages)")
    
    # Формируем текст от пользователя (новые сообщения)
    joined_user_text = "\n\n".join(
        f"[{m.date.strftime('%Y-%m-%d %H:%M:%S')}] {m.text.strip()}" 
        for m in batch if (m.text or "").strip()
    )
    
    # Формируем запрос к GPT
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Добавляем историю, но исключаем последние сообщения которые уже в batch
    # Это предотвращает дублирование
    if telegram_history:
        # Берём историю кроме последних N сообщений (где N = len(batch))
        # т.к. batch содержит последние входящие сообщения
        history_without_batch = history[:-len(batch)] if len(batch) > 0 else history
        messages.extend(history_without_batch)
    else:
        messages.extend(history)
    
    # Добавляем новые сообщения от пользователя
    messages.append({"role": "user", "content": joined_user_text})
    
    # Генерируем ответ
    reply = await openai_generate(messages)
    
    if not reply and OPENAI_CFG.get("USE_FALLBACK_ON_OPENAI_FAIL"):
        reply = OPENAI_CFG.get("FALLBACK_TEXT", "")
    
    if not reply:
        return False
    
    # Отправляем ответ
    try:
        await client.send_message(uid, reply)
        log_info(f"{session_name}: sent reply to {uid}")
    except Exception as e:
        log_error(f"{session_name}: reply failed in chat {uid}: {e!r}")
        return False
    
    # Сохраняем в историю
    for m in batch:
        text = (m.text or "").strip()
        if text:
            convo_append(session_name, uid, "user", text, username)
    convo_append(session_name, uid, "assistant", reply, username)
    
    # Проверяем триггерные фразы
    low_reply = reply.lower()
    pos_phrase = OPENAI_CFG["TRIGGER_PHRASES"]["POSITIVE"].lower()
    neg_phrase = OPENAI_CFG["TRIGGER_PHRASES"]["NEGATIVE"].lower()
    
    # Получаем информацию о пользователе для пересылки
    user = None
    try:
        user = await client.get_entity(uid)
    except:
        pass
    
    # Флаг, был ли пользователь помечен как processed
    was_processed = False
    
    if pos_phrase in low_reply:
        if not already_processed(uid):
            await forward_conversation(client, uid, "POSITIVE", user)
            if user:
                await mark_processed(client, user, uid)
            was_processed = True
            log_info(f"{session_name}: user {uid} marked as POSITIVE, stopping replies")
    elif neg_phrase in low_reply:
        if not already_processed(uid):
            await forward_conversation(client, uid, "NEGATIVE", user)
            if user:
                await mark_processed(client, user, uid)
            was_processed = True
            log_info(f"{session_name}: user {uid} marked as NEGATIVE, stopping replies")
    
    return was_processed

async def handle_chat_session(
    client: TelegramClient, 
    chat_id: int, 
    unread_hint: int,
    session_name: str
) -> None:
    """Обрабатывает один чат с ожиданием новых сообщений в окне"""
    uid = chat_id
    
    # Получаем username пользователя для файла диалога
    username = None
    try:
        user = await client.get_entity(uid)
        if hasattr(user, 'username') and user.username:
            username = user.username
    except:
        pass
    
    # Проверяем, писали ли мы в этот диалог ранее
    if REPLY_ONLY_IF_PREV:
        has_out = await _has_outgoing_before(client, uid)
        if not has_out:
            log_info(f"{session_name}: skip {uid} — no previous outgoing")
            return
    
    # Собираем входящие сообщения
    take = max(1, min(unread_hint or 0, 20)) or 10
    incoming = await _collect_incoming_slice(client, uid, max_take=take)
    incoming = [m for m in incoming if (m.text or "").strip()]
    
    if not incoming:
        return
    
    # Отвечаем на первый батч
    was_processed = await _reply_once_for_batch(client, uid, incoming, session_name, username)
    
    # Если пользователь был помечен как processed, останавливаем обработку
    if was_processed:
        log_info(f"{session_name}: user {uid} processed, exiting chat session")
        return
    
    last_confirmed_id = incoming[-1].id
    
    # Цикл ожидания новых сообщений
    while True:
        # Случайное окно ожидания из диапазона
        window_sec = random.uniform(*DIALOG_WAIT_WINDOW_RANGE)
        eta = (_get_local_time() + datetime.timedelta(seconds=window_sec)).strftime("%H:%M:%S")
        log_info(f"{session_name}: stay in chat {uid} for {window_sec:.1f}s (until ~{eta} MSK)")
        
        # Просто ждём указанное время (имитация что человек отошёл)
        await asyncio.sleep(window_sec)
        
        # Проверяем новые сообщения ПОСЛЕ ожидания
        fresh = await _collect_new_incoming_since(client, uid, last_confirmed_id, max_take=50)
        
        # Если новых сообщений нет, выходим
        if not fresh:
            log_info(f"{session_name}: done waiting in chat {uid} (no new messages in window)")
            return
        
        # Отвечаем на новые сообщения
        was_processed = await _reply_once_for_batch(client, uid, fresh, session_name, username)
        
        # Если пользователь был помечен как processed, останавливаем обработку
        if was_processed:
            log_info(f"{session_name}: user {uid} processed during window, exiting chat session")
            return
        
        # Обновляем ID последнего обработанного сообщения
        last_confirmed_id = fresh[-1].id
        
        log_info(f"{session_name}: replied to new messages in chat {uid}, opening new window")

# ======================== POLL CLIENT ========================
async def poll_client(client: TelegramClient, session_name: str):
    """Обрабатывает все непрочитанные диалоги на одном аккаунте"""
    log_info(f"[{session_name}] poll started")
    
    try:
        processed_any_chat = False
        
        # Получаем диалоги (оптимизация: один запрос вместо множества)
        dialogs = await client.get_dialogs(limit=100)
        
        for dialog in dialogs:
            # Фильтруем только приватные чаты
            if not isinstance(dialog.entity, User):
                continue
            
            uid = dialog.entity.id
            
            # Пропускаем обработанных
            if already_processed(uid):
                continue
            
            # Проверяем количество непрочитанных
            unread = dialog.unread_count
            if unread <= 0:
                continue
            
            processed_any_chat = True
            
            # Обрабатываем чат
            await handle_chat_session(client, uid, unread, session_name)
        
        if not processed_any_chat:
            log_info(f"[{session_name}] no new messages on this account")
    
    except FloodWaitError as e:
        log_error(f"{session_name}: FloodWait {e.seconds}s, skipping this round")
        await asyncio.sleep(e.seconds)
    
    except Exception as e:
        log_error(f"{session_name}: poll_client error: {e!r}")

# ======================== SESSION CONVERTER ========================
def auto_fix_session(session_path: str) -> bool:
    """
    Автоматически исправляет файл сессии если он в старом формате (6 столбцов)
    Конвертирует в новый формат (5 столбцов) для совместимости с Python 3.13+
    
    БЕЗОПАСНОСТЬ:
    - Не изменяет auth_key (ключ авторизации)
    - Не изменяет dc_id, server_address, port
    - Только удаляет неиспользуемый 6-й столбец из локальной SQLite базы
    - Telegram API видит только auth_key, структура БД не передается на сервер
    - Это чисто локальное изменение формата хранения
    """
    session_file = session_path + ".session"
    
    if not os.path.exists(session_file):
        return True  # Файл не существует, это нормально для новых сессий
    
    try:
        # Подключаемся к SQLite
        conn = sqlite3.connect(session_file)
        cursor = conn.cursor()
        
        # Проверяем количество столбцов в таблице sessions
        cursor.execute("PRAGMA table_info(sessions)")
        columns = cursor.fetchall()
        
        if len(columns) == 6:
            # Нужна конвертация
            log_info(f"Auto-fixing session format: {os.path.basename(session_file)}")
            
            # Создаем backup (только если еще нет)
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
                log_info(f"Session fixed successfully: {os.path.basename(session_file)}")
        
        elif len(columns) == 5:
            # Уже правильный формат
            pass
        else:
            log_error(f"Unexpected session format ({len(columns)} columns): {session_file}")
            conn.close()
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        log_error(f"Failed to check/fix session {session_file}: {e!r}")
        return False

# ======================== PROXY STATUS TRACKING ========================
# Глобальный словарь для отслеживания статуса прокси для каждой сессии
# Формат: {session_name: {"proxy_required": bool, "proxy_ok": bool, "proxy_dict": dict}}
PROXY_STATUS = {}

# ======================== SESSION SETUP ========================
async def setup_clients():
    """Настраивает клиенты из сессий и прокси"""
    print("\n" + "="*80)
    print("SETUP_CLIENTS STARTED")
    print("="*80)
    
    DATA_DIR = "data"
    SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
    
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"SESSIONS_DIR: {SESSIONS_DIR}")
    print(f"Current working directory: {os.getcwd()}")
    
    # Создаем папку для сессий если её нет
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    # Загружаем API credentials
    api_map = {}
    print(f"\nSearching for api_map.txt...")
    print(f"api_map.txt exists: {os.path.exists('api_map.txt')}")
    
    if os.path.exists("api_map.txt"):
        with open("api_map.txt", encoding="utf-8") as f:
            content = f.read()
        print(f"api_map.txt content ({len(content)} bytes):")
        print(content)
        print()
        
        for line in content.splitlines():
            p = line.strip().split()
            if len(p) >= 3:
                api_map[os.path.splitext(p[0])[0]] = (int(p[1]), p[2])
                print(f"  Loaded: {p[0]} -> api_id={p[1]}, api_hash={p[2][:10]}...")
    else:
        print("  ✗ api_map.txt NOT FOUND!")
    
    # Находим все сессии в папке sessions
    # Также проверяем старую папку data для обратной совместимости
    print(f"\nSearching for .session files...")
    print(f"SESSIONS_DIR exists: {os.path.exists(SESSIONS_DIR)}")
    
    sessions = []
    if os.path.exists(SESSIONS_DIR):
        all_files = os.listdir(SESSIONS_DIR)
        print(f"Files in {SESSIONS_DIR}: {all_files}")
        sessions.extend([f for f in all_files if f.endswith(".session")])
        print(f"Found {len(sessions)} .session files in {SESSIONS_DIR}")
    
    # Проверяем старую папку для миграции
    if os.path.exists(DATA_DIR):
        old_sessions = [f for f in os.listdir(DATA_DIR) if f.endswith(".session")]
        if old_sessions:
            print(f"Found {len(old_sessions)} .session files in old {DATA_DIR}")
        for old_sess in old_sessions:
            if old_sess not in sessions:  # Только если еще нет в новой папке
                sessions.append(old_sess)
    sessions.sort()
    
    print(f"\nTotal sessions to process: {len(sessions)}")
    if sessions:
        for s in sessions:
            print(f"  - {s}")
    
    # Загружаем прокси
    proxy_lines = load_proxies_from_file("proxies.txt")
    
    clients = []
    
    for idx, file in enumerate(sessions):
        name = os.path.splitext(file)[0]
        
        # Путь к сессии - сначала ищем в новой папке, потом в старой
        session_path = os.path.join(SESSIONS_DIR, name)
        if not os.path.exists(session_path + ".session"):
            # Проверяем старую папку
            old_path = os.path.join(DATA_DIR, name)
            if os.path.exists(old_path + ".session"):
                session_path = old_path
        
        # Получаем API credentials
        creds = api_map.get(name)
        json_proxy = None  # Прокси из JSON файла
        
        # ВСЕГДА пытаемся прочитать JSON (для прокси даже если есть api_map)
        json_path = os.path.join(SESSIONS_DIR, f"{name}.json")
        if not os.path.exists(json_path):
            # Потом в старой папке data
            json_path = os.path.join(DATA_DIR, f"{name}.json")
        
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    jdata = json.load(jf)
                
                # Если нет creds из api_map - берем из JSON
                if not creds:
                    app_id = jdata.get("app_id") or jdata.get("api_id")
                    app_hash = jdata.get("app_hash") or jdata.get("api_hash")
                    if app_id and app_hash:
                        creds = (int(app_id), app_hash)
                        log_info(f"{name}: loaded api_id/hash from {json_path}")
                
                # Проверяем наличие прокси в JSON (ВСЕГДА)
                if jdata.get("proxy") and jdata["proxy"] != "null":
                    json_proxy = jdata["proxy"]
                    log_info(f"{name}: found proxy in JSON: {json_proxy}")
            except Exception as e:
                log_error(f"{name}: failed to read {json_path}: {e!r}")
        
        if not creds:
            log_error(f"{name}: missing API creds, skipped")
            continue
        
        api_id, api_hash = creds
        
        # Настраиваем прокси (приоритет: JSON > proxies.txt)
        proxy_dict = None
        
        # Сначала пробуем прокси из JSON
        if json_proxy:
            proxy_dict = parse_proxy_url(json_proxy)
            if proxy_dict:
                log_info(f"{name}: using proxy from JSON")
        
        # Если прокси нет в JSON, используем proxies.txt
        if not proxy_dict and proxy_lines:
            proxy_str = proxy_lines[idx % len(proxy_lines)]
            proxy_dict = parse_proxy_url(proxy_str)
            if proxy_dict:
                log_info(f"{name}: using proxy from proxies.txt")
        
        # Обрабатываем прокси
        proxy_required = proxy_dict is not None  # Если прокси настроена, она обязательна
        proxy_ok = False
        
        if proxy_dict:
            # Извлекаем для логирования
            addr = proxy_dict.get('addr', 'unknown')
            port = proxy_dict.get('port', 0)
            username = proxy_dict.get('username')
            
            # Проверяем прокси перед использованием
            log_info(f"🔍 {name}: проверка прокси {addr}:{port}...")
            
            if await check_proxy_connection(proxy_dict):
                log_info(
                    f"✅ {name}: прокси {addr}:{port} работает корректно "
                    f"(user: {username if username else 'нет авторизации'})"
                )
                proxy_ok = True
            else:
                log_error(
                    f"❌ {name}: прокси {addr}:{port} НЕ РАБОТАЕТ!\n"
                    f"  ⏭ Аккаунт будет пропускаться пока прокси не заработает.\n"
                    f"  🔄 Проверка будет повторяться в каждом цикле."
                )
                proxy_ok = False
        else:
            # КРИТИЧНО: Если прокси не настроена - ПРОПУСКАЕМ аккаунт!
            log_error(f"⚠️ {name}: ПРОКСИ НЕ НАСТРОЕНА! Аккаунт будет ПРОПУЩЕН для безопасности.")
            proxy_required = True  # Прокси ОБЯЗАТЕЛЬНА
            proxy_ok = False  # Прокси НЕ работает (её нет)
        
        # Сохраняем статус прокси для этой сессии
        PROXY_STATUS[name] = {
            "proxy_required": proxy_required,
            "proxy_ok": proxy_ok,
            "proxy_dict": proxy_dict
        }
        
        # Автоматически исправляем формат сессии если нужно
        if not auto_fix_session(session_path):
            log_error(f"{name}: session format check/fix failed, skipping")
            continue
        
        # Создаем клиент
        # ВАЖНО: connection_retries=1 - только 1 попытка подключения без retry
        try:
            cl = TelegramClient(
                session_path,
                api_id,
                api_hash,
                proxy=proxy_dict,
                connection_retries=1,  # Только 1 попытка подключения!
                retry_delay=0,         # Без задержки
                timeout=10             # Таймаут 10 секунд
            )
            clients.append((cl, name))
        except Exception as e:
            log_error(f"{name}: failed to create client: {e!r}")
    
    return clients

# ======================== MAIN ========================
async def main():
    """Основной цикл программы"""
    
    clients = await setup_clients()
    if not clients:
        log_error("No clients configured, exiting.")
        return
    
    log_info(f"Summary: configured {len(clients)} sessions. Running sequentially (connect -> process -> disconnect)...")
    
    # Показываем настроенные периоды сна если есть
    if SLEEP_PERIODS:
        log_info(f"Sleep periods configured: {', '.join(SLEEP_PERIODS)}")
    
    while True:
        # Проверяем, не время ли сна
        if is_sleep_time():
            await wait_until_wake_time()
        
        # Обрабатываем аккаунты по очереди
        for cl, name in clients:
            try:
                # Проверяем статус прокси перед обработкой
                proxy_status = PROXY_STATUS.get(name, {})
                proxy_required = proxy_status.get("proxy_required", False)
                proxy_ok = proxy_status.get("proxy_ok", True)
                proxy_dict = proxy_status.get("proxy_dict", None)
                
                # Если прокси требуется, но не работает - пытаемся переподключиться
                if proxy_required and not proxy_ok:
                    log_info(f"{name}: proxy required but unavailable, attempting to reconnect...")
                    
                    if proxy_dict:
                        addr = proxy_dict.get('addr', 'unknown')
                        port = proxy_dict.get('port', 0)
                        
                        # Пробуем снова проверить прокси
                        log_info(f"🔄 {name}: проверка прокси {addr}:{port}...")
                        if await check_proxy_connection(proxy_dict):
                            log_info(
                                f"✅ {name}: прокси {addr}:{port} теперь доступна!\n"
                                f"  Переподключаем аккаунт с рабочей прокси..."
                            )
                            PROXY_STATUS[name]["proxy_ok"] = True
                            proxy_ok = True
                            
                            # Пересоздаем клиент с рабочей прокси
                            api_id = cl.api_id
                            api_hash = cl.api_hash
                            session_path = cl.session.filename
                            
                            try:
                                await cl.disconnect()
                            except:
                                pass
                            
                            cl = TelegramClient(
                                session_path, api_id, api_hash, 
                                proxy=proxy_dict,
                                connection_retries=1,
                                retry_delay=0,
                                timeout=10
                            )
                            # Обновляем клиент в списке
                            for i, (c, n) in enumerate(clients):
                                if n == name:
                                    clients[i] = (cl, name)
                                    break
                        else:
                            log_error(
                                f"❌ {name}: прокси {addr}:{port} всё ещё недоступна\n"
                                f"  ⏭ Пропускаем аккаунт в этом цикле.\n"
                                f"  🔄 Повторная проверка при следующей итерации."
                            )
                            continue  # Пропускаем обработку этого аккаунта
                    else:
                        log_error(f"{name}: proxy required but no proxy configured - skipping")
                        continue
                
                # Если прокси не требуется или работает - продолжаем обработку
                if not proxy_required or proxy_ok:
                    # БЫСТРАЯ проверка прокси перед подключением (1 попытка, 5 сек)
                    if proxy_dict:
                        addr = proxy_dict.get('addr', 'unknown')
                        port = proxy_dict.get('port', 0)
                        log_info(f"{name}: быстрая проверка прокси {addr}:{port}...")
                        
                        if not await check_proxy_connection(proxy_dict):
                            log_error(
                                f"⏭ {name}: прокси недоступна - ПРОПУСК аккаунта\n"
                                f"  Прокси: {addr}:{port}"
                            )
                            PROXY_STATUS[name]["proxy_ok"] = False
                            continue  # Сразу пропускаем, без retry
                    
                    # Подключаемся
                    await cl.start()
                    me = await cl.get_me()
                    log_info(f"{name}: connected as @{me.username or me.id}")
                    
                    # Обрабатываем все диалоги на аккаунте
                    await poll_client(cl, name)
            
            except PhoneNumberBannedError as e:
                log_error(
                    f"🚫 {name}: НОМЕР ТЕЛЕФОНА ЗАБАНЕН!\n"
                    f"  ❌ Этот аккаунт ПЕРМАНЕНТНО заблокирован Telegram.\n"
                    f"  ❌ Восстановление невозможно.\n"
                    f"  ⚠️ РЕКОМЕНДАЦИЯ: Удалите этот аккаунт из кампании.\n"
                    f"  Error: {e!r}"
                )
            
            except UserDeactivatedBanError as e:
                log_error(
                    f"🚫 {name}: АККАУНТ ДЕАКТИВИРОВАН (БАН)!\n"
                    f"  ❌ Аккаунт заблокирован за нарушение правил Telegram.\n"
                    f"  ❌ Восстановление маловероятно.\n"
                    f"  ⚠️ РЕКОМЕНДАЦИЯ: Обратитесь в поддержку Telegram или удалите аккаунт.\n"
                    f"  Error: {e!r}"
                )
            
            except UserDeactivatedError as e:
                log_error(
                    f"⚠️ {name}: АККАУНТ ДЕАКТИВИРОВАН!\n"
                    f"  ⚠️ Аккаунт отключен (возможно временно).\n"
                    f"  📱 Попробуйте войти через официальный Telegram.\n"
                    f"  ⚠️ РЕКОМЕНДАЦИЯ: Проверьте статус в официальном приложении.\n"
                    f"  Error: {e!r}"
                )
            
            except AuthKeyUnregisteredError as e:
                log_error(
                    f"⚠️ {name}: КЛЮЧ АВТОРИЗАЦИИ НЕ ЗАРЕГИСТРИРОВАН!\n"
                    f"  ⚠️ Возможные причины:\n"
                    f"  1. Аккаунт был удалён\n"
                    f"  2. Сессия устарела (слишком долго не использовалась)\n"
                    f"  3. Аккаунт заморожен/забанен\n"
                    f"  ⚠️ РЕКОМЕНДАЦИЯ: Требуется повторная авторизация.\n"
                    f"  Error: {e!r}"
                )
            
            except UnauthorizedError as e:
                log_error(
                    f"⚠️ {name}: СЕССИЯ НЕ АВТОРИЗОВАНА - ВОЗМОЖНЫЕ ПРИЧИНЫ:\n"
                    f"  1. Аккаунт ЗАМОРОЖЕН/ЗАБАНЕН Telegram\n"
                    f"  2. Сессия устарела или невалидна\n"
                    f"  3. Требуется повторный вход\n"
                    f"  ⚠️ РЕКОМЕНДАЦИЯ: Проверьте статус аккаунта в официальном Telegram!\n"
                    f"  Error details: {e!r}"
                )
            
            except FloodWaitError as e:
                wait_seconds = e.seconds
                log_error(
                    f"⚠️ {name}: FLOODWAIT - Telegram ограничил действия на {wait_seconds} секунд\n"
                    f"  Это НЕ бан, просто временное ограничение.\n"
                    f"  Аккаунт будет пропущен в этом цикле."
                )
            
            except asyncio.CancelledError as e:
                log_error(f"⏭ {name}: CancelledError - ПРОПУСК (прокси/сеть)")
                if name in PROXY_STATUS:
                    PROXY_STATUS[name]["proxy_ok"] = False
            
            except asyncio.TimeoutError as e:
                log_error(f"⏭ {name}: Timeout - ПРОПУСК (прокси не отвечает)")
                if name in PROXY_STATUS:
                    PROXY_STATUS[name]["proxy_ok"] = False
            
            except ConnectionError as e:
                log_error(f"⏭ {name}: ConnectionError - ПРОПУСК (нет соединения)")
                if name in PROXY_STATUS:
                    PROXY_STATUS[name]["proxy_ok"] = False
            
            except OSError as e:
                log_error(f"⏭ {name}: OSError - ПРОПУСК (сетевая ошибка: {type(e).__name__})")
                if name in PROXY_STATUS:
                    PROXY_STATUS[name]["proxy_ok"] = False
            
            except Exception as e:
                log_error(f"{name}: fatal error while processing: {e!r}")
            
            finally:
                # Отключаемся только если мы подключались
                try:
                    if cl.is_connected():
                        await cl.disconnect()
                        log_info(f"{name}: disconnected")
                except Exception as e2:
                    log_error(f"{name}: error on disconnect: {e2!r}")
                
                # Вычисляем задержку перед следующим аккаунтом с разбросом
                base_delay = random.uniform(*ACCOUNT_LOOP_DELAY_RANGE)
                variance = base_delay * 0.25 * random.uniform(-1, 1)
                delay = max(0, base_delay + variance)
                
                # Логируем СРАЗУ после отключения, до задержки
                eta_round = (
                    _get_local_time() + datetime.timedelta(seconds=delay)
                ).strftime("%H:%M:%S")
                log_info(f"next account in {delay:.1f}s (at ~{eta_round} MSK)")
                
                # Теперь делаем саму задержку
                await asyncio.sleep(delay)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("Program stopped by user")
    except asyncio.CancelledError:
        log_error("Program cancelled (CancelledError in main loop)")
        # Выходим с кодом 0 - это не критическая ошибка
        sys.exit(0)
    except Exception as e:
        log_error(f"Fatal error: {e!r}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
