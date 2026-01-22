from models import db, Post, VKStatistic, VKAccount
from sqlalchemy import func
from datetime import datetime, timedelta
import base64
from io import BytesIO
import matplotlib.pyplot as plt

def get_overall_statistics(user_id):
    """Сводные данные для 4-х верхних плиток"""
    # Считаем общие охваты и вовлеченность из таблицы статистики
    stats = db.session.query(
        func.sum(VKStatistic.reach).label('total_reach'),
        func.sum(VKStatistic.engagement).label('total_eng')
    ).join(VKAccount).filter(VKAccount.user_id == user_id).first()

    # Считаем общее кол-во лайков и постов
    posts_data = db.session.query(
        func.count(Post.id).label('count'),
        func.sum(Post.likes).label('likes')
    ).filter(Post.user_id == user_id, Post.is_published == True).first()

    return {
        'total_reach': stats.total_reach or 0,
        'engagement_rate': stats.total_eng or 0,
        'total_posts': posts_data.count or 0,
        'total_likes': posts_data.likes or 0
    }

def get_top_posts(user_id):
    """Список лучших постов по просмотрам"""
    return Post.query.filter_by(user_id=user_id, is_published=True)\
               .order_by(Post.views.desc())\
               .limit(5).all()

def get_growth_data(user_id):
    """Данные для графика роста (просмотры по дням за неделю)"""
    last_7_days = datetime.utcnow() - timedelta(days=7)
    
    daily_data = db.session.query(
        func.date(Post.publish_date).label('date'),
        func.sum(Post.views).label('views')
    ).filter(
        Post.user_id == user_id, 
        Post.is_published == True,
        Post.publish_date >= last_7_days
    ).group_by(func.date(Post.publish_date)).all()

    return daily_data

def get_audience_data(user_id):
    """Данные по демографии для круговой диаграммы"""
    stat = VKStatistic.query.join(VKAccount)\
               .filter(VKAccount.user_id == user_id)\
               .order_by(VKStatistic.updated_at.desc()).first()
    
    if not stat:
        return {'male': 50, 'female': 50}
    
    return {
        'male': stat.male_percentage or 0,
        'female': stat.female_percentage or 0
    }

# Вспомогательная функция для генерации картинки графика (Matplotlib)
def generate_growth_chart(data):
    if not data: return None
    
    plt.figure(figsize=(8, 4))
    dates = [d.date for d in data]
    views = [d.views for d in data]
    
    plt.plot(dates, views, marker='o', color='#4e73df', linewidth=2)
    plt.fill_between(dates, views, color='#4e73df', alpha=0.1)
    plt.axis('off') # Убираем рамки для красоты
    
    buf = BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# Аналогично добавь заглушки для других чартов или используй JSON для Chart.js
def generate_audience_chart(data):
    return None # Если используешь Chart.js на фронте, картинка не нужна

def generate_engagement_chart(user_id):
    return None