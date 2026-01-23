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


class FollowUpSettings(BaseModel):
    """Настройки follow-up сообщений"""
    enabled: bool = False
    delay_hours: int = 24  # Через сколько часов отправлять follow-up
    prompt: str = "Напиши короткое напоминание о себе. Вежливо напомни о предложении и спроси, актуально ли оно ещё. Если не актуально - попроси сообщить об этом. Сообщение должно быть кратким (2-3 предложения)."
    # Промпт для генерации follow-up сообщения через GPT с учётом контекста диалога


class TelegramSettings(BaseModel):
    forward_limit: int = 5
    reply_only_if_previously_wrote: bool = True
    history_limit: int = 20
    pre_read_delay_range: List[float] = [5, 10]
    read_reply_delay_range: List[float] = [5, 10]
    account_loop_delay_range: List[float] = [300, 600]  # Задержка между аккаунтами (5-10 минут)
    dialog_wait_window_range: List[float] = [40, 60]
    sleep_periods: List[str] = ["00:00-15:00", "19:00-00:00"]  # Периоды сна
    timezone_offset: int = 3
    ignore_bot_usernames: bool = True  # Не отвечать ботам (username начинается на i7/i8)
    follow_up: FollowUpSettings = FollowUpSettings()  # Настройки follow-up


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


class DialogStatus(str, Enum):
    """Статус диалога для маркировки лидов"""
    NONE = "none"  # Не размечен
    LEAD = "lead"  # Лид (потенциальный клиент)
    NOT_LEAD = "not_lead"  # Не лид
    LATER = "later"  # Обработать позже


class Dialog(BaseModel):
    session_name: str
    user_id: int
    username: Optional[str] = None
    messages: List[DialogMessage]
    last_message_time: Optional[datetime] = None  # Время последнего сообщения
    status: DialogStatus = DialogStatus.NONE  # Статус диалога (лид/не лид/потом)


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

