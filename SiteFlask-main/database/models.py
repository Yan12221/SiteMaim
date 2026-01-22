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