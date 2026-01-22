import os
from datetime import datetime

from flask import json
from database import db
from flask_login import UserMixin
from sqlalchemy import create_engine

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

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    vk_accounts = db.relationship('VKAccount', backref='user', lazy=True)
    campaigns = db.relationship('Campaign', backref='user', lazy=True)
    
    theme_mode = db.Column(db.String(10), default='light')

class VKAccount(db.Model):
    __tablename__ = 'vk_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.String(50), nullable=False)
    group_name = db.Column(db.String(200))
    access_token = db.Column(db.Text, nullable=False)
    user_token = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    statistics = db.relationship('VKStatistic', backref='vk_account', lazy=True)
    posts = db.relationship('Post', backref='vk_account', lazy=True)

class VKStatistic(db.Model):
    __tablename__ = 'vk_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    vk_account_id = db.Column(db.Integer, db.ForeignKey('vk_accounts.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    
    # Основные метрики
    followers_count = db.Column(db.Integer, default=0)
    followers_growth = db.Column(db.Integer, default=0)
    reach = db.Column(db.Integer, default=0)
    engagement = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    ctr = db.Column(db.Float, default=0.0)
    
    # Аудитория
    male_percentage = db.Column(db.Float, default=0.0)
    female_percentage = db.Column(db.Float, default=0.0)
    age_18_24 = db.Column(db.Float, default=0.0)
    age_25_34 = db.Column(db.Float, default=0.0)
    age_35_44 = db.Column(db.Float, default=0.0)
    age_45_plus = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class Campaign(db.Model):
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(200))
    status = db.Column(db.String(50), default='active')  # active, completed, paused
    total_posts = db.Column(db.Integer, default=0)
    published_posts = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    
    # Результаты
    total_reach = db.Column(db.Integer, default=0)
    total_engagement = db.Column(db.Integer, default=0)
    total_followers_growth = db.Column(db.Integer, default=0)
    
    # Связи
    posts = db.relationship('Post', backref='campaign', lazy=True)

class Post(db.Model):
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    vk_account_id = db.Column(db.Integer, db.ForeignKey('vk_accounts.id'), nullable=False)
    
    # Контент
    text = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(50), nullable=True)  # nullable=True
    hashtags = db.Column(db.Text, nullable=True)  # nullable=True
    
    # Время - ВАЖНОЕ ИЗМЕНЕНИЕ!
    scheduled_time = db.Column(db.DateTime, nullable=True)  # ДОЛЖНО БЫТЬ nullable=True
    published_time = db.Column(db.DateTime, nullable=True)  # nullable=True
    
    # Статус
    status = db.Column(db.String(50), default='published')
    
    # Статистика после публикации
    vk_post_id = db.Column(db.String(100), nullable=True)
    reach = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


    is_published = db.Column(db.Boolean, default=False)
    publish_date = db.Column(db.DateTime, nullable=True)
    title = db.Column(db.String(200), nullable=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    def __repr__(self):
        return f'<Post {self.id} {self.text[:50]}>'
    
class BusinessProfile(db.Model):
    __tablename__ = 'business_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Информация о бизнесе
    business_name = db.Column(db.String(200))
    niche = db.Column(db.String(200))          # Ниша (что продают)
    description = db.Column(db.Text)           # Описание продукта
    target_audience = db.Column(db.Text)       # Целевая аудитория
    goals = db.Column(db.Text)                 # Цели проекта
    tone_of_voice = db.Column(db.String(100))  # Тон общения (формальный, дружеский и т.д.)
    stop_words = db.Column(db.Text)            # Стоп-слова для контента
    
    BusinessPrompt = db.Column(db.Text)          # Промпт для AI на основе профиля
    # API ключи (например, для AI сервисов)
    openai_api_key = db.Column(db.String(200), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class PostTheme(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    theme_text = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f'<PostTheme {self.theme_text[:20]}...>'
    
class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'
    
    # ОБЯЗАТЕЛЬНО: Первичный ключ
    id = db.Column(db.Integer, primary_key=True)
    
    # Исправлено: 'users.id' вместо 'user.id'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    post_title = db.Column(db.String(255))
    passed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Float)
    
    # Храним детальные ошибки и советы в формате JSON
    issues = db.Column(db.Text) 
    suggestions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_issues(self, issues_list):
        self.issues = json.dumps(issues_list, ensure_ascii=False)

    def get_issues(self):
        return json.loads(self.issues) if self.issues else []
    
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class ScheduledPost(Base):
    """Модель запланированного поста"""
    __tablename__ = 'scheduled_posts'
    
    id = Column(String, primary_key=True)
    business_id = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    platforms = Column(JSON, nullable=False)
    status = Column(String, default='scheduled')
    created_at = Column(DateTime, default=datetime.now)
    published_at = Column(DateTime, nullable=True)

class ModerationLog(Base):
    """Лог модерации контента"""
    __tablename__ = 'moderation_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String, nullable=False)
    business_id = Column(String, nullable=False)
    passed = Column(Integer, nullable=False)  # 0 или 1
    score = Column(Float, nullable=False)
    issues = Column(JSON, nullable=True)
    suggestions = Column(JSON, nullable=True)
    check_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class PublishedContent(Base):
    """История опубликованного контента"""
    __tablename__ = 'published_content'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String, nullable=False)
    business_id = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    platforms = Column(JSON, nullable=False)
    published_at = Column(DateTime, default=datetime.now)
    analytics = Column(JSON, nullable=True)

# Создание БД
engine = create_engine('sqlite:///content_platform.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
