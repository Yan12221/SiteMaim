import os
from dataclasses import dataclass
from typing import List

# Получаем ссылку из Vercel, если её нет — используем sqlite (для локального запуска)
db_url = os.environ.get('DATABASE_URL')

if db_url:
    # Исправление для некоторых версий SQLAlchemy (postgres -> postgresql)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)
else:
    # Локально на компе будет работать SQLite
    engine = create_engine('sqlite:///content_platform.db')
    
@dataclass
class AIConfig:
    """Конфигурация для AI моделей"""
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    MODEL_NAME: str = "gpt-5-nano"

@dataclass
class ModeratorConfig:
    """Настройки модератора"""
    SIMILARITY_THRESHOLD: float = 0.75  # Порог схожести тем
    MIN_BRAND_SCORE: float = 0.6  # Минимальный балл соответствия бренду
    MIN_TOPIC_SCORE: float = 0.7  # Минимальный балл по теме
    
@dataclass
class SchedulerConfig:
    """Настройки планировщика"""
    DEFAULT_POSTS_PER_WEEK: int = 7
    POSTING_TIMES: List[str] = None
    TIMEZONE: str = "Europe/Moscow"
    
    def __post_init__(self):
        if self.POSTING_TIMES is None:
            self.POSTING_TIMES = ["09:00", "13:00", "18:00", "21:00"]

@dataclass
class SocialNetworksConfig:
    """API ключи социальных сетей"""
    VK_ACCESS_TOKEN: str = os.getenv('VK_ACCESS_TOKEN', '')
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    DZEN_TOKEN: str = os.getenv('DZEN_TOKEN', '')
    OK_ACCESS_TOKEN: str = os.getenv('OK_ACCESS_TOKEN', '')
    X_API_KEY: str = os.getenv('X_API_KEY', '')
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
    FACEBOOK_ACCESS_TOKEN: str = os.getenv('FACEBOOK_ACCESS_TOKEN', '')

# Инициализация конфигов
ai_config = AIConfig()
moderator_config = ModeratorConfig()
scheduler_config = SchedulerConfig()
social_config = SocialNetworksConfig()
