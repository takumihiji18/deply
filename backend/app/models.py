from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class CampaignStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class ProxyItem(BaseModel):
    """Модель для хранения прокси"""
    id: str  # Уникальный ID прокси
    url: str  # socks5://user:pass@host:port или http://...
    name: Optional[str] = None  # Пользовательское имя прокси (опционально)
    is_active: bool = True


class Account(BaseModel):
    session_name: str
    api_id: int
    api_hash: str
    phone: Optional[str] = None
    proxy: Optional[str] = None  # Старое поле для совместимости (ID прокси или URL)
    proxy_id: Optional[str] = None  # ID привязанного прокси из списка
    is_active: bool = True


class OpenAISettings(BaseModel):
    api_key: str
    model: str = "gpt-4"
    proxy: Optional[str] = None
    system_prompt: str
    project_name: str = ""
    trigger_phrases_positive: str = "Отлично, рад, что смог вас заинтересовать"
    trigger_phrases_negative: str = "Вижу, что не смог вас заинтересовать"
    target_chats_positive: str = ""
    target_chats_negative: str = ""
    use_fallback_on_fail: bool = False
    fallback_text: str = ""


class TelegramSettings(BaseModel):
    forward_limit: int = 5
    reply_only_if_previously_wrote: bool = True
    history_limit: int = 20
    pre_read_delay_range: List[float] = [5, 10]
    read_reply_delay_range: List[float] = [5, 10]
    account_loop_delay_range: List[float] = [90, 180]
    check_new_msg_interval_range: List[float] = [7, 12]
    dialog_wait_window_range: List[float] = [40, 60]
    sleep_periods: List[str] = ["20:00-08:00", "13:00-14:30"]
    timezone_offset: int = 3


class Campaign(BaseModel):
    id: str
    name: str
    status: CampaignStatus = CampaignStatus.STOPPED
    accounts: List[Account] = []
    openai_settings: OpenAISettings
    telegram_settings: TelegramSettings
    work_folder: str
    processed_clients_file: str
    proxy_list: str = ""  # Старое поле для совместимости (deprecated)
    proxies: List[ProxyItem] = []  # Новый список прокси как структурированные данные
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class CampaignCreate(BaseModel):
    name: str
    openai_settings: OpenAISettings
    telegram_settings: Optional[TelegramSettings] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[CampaignStatus] = None
    accounts: Optional[List[Account]] = None
    openai_settings: Optional[OpenAISettings] = None
    telegram_settings: Optional[TelegramSettings] = None
    proxy_list: Optional[str] = None  # Deprecated
    proxies: Optional[List[ProxyItem]] = None  # Новый список прокси


class DialogMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class Dialog(BaseModel):
    session_name: str
    user_id: int
    username: Optional[str] = None
    messages: List[DialogMessage]


class ProcessedClient(BaseModel):
    user_id: int
    username: Optional[str] = None
    processed_at: Optional[datetime] = None
    campaign_id: str


class CampaignStats(BaseModel):
    campaign_id: str
    total_dialogs: int
    total_processed: int
    active_sessions: int
    status: CampaignStatus
    last_activity: Optional[datetime] = None

