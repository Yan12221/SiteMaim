from flask import Blueprint, jsonify, session
from models import VKAccount, VKStatistic, Post, db # Добавил db сюда
from datetime import datetime
from sqlalchemy import desc, func

# Импортируем твои функции сервиса
from routes.dashboard_service import get_overall_statistics, get_growth_data

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/unified-stats')
def api_unified_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    try:
        # 1. Используем твою функцию из dashboard_service.py
        stats = get_overall_statistics(user_id)
        
        # 2. Добавляем кол-во аккаунтов (для первой плитки)
        stats['total_accounts'] = VKAccount.query.filter_by(
            user_id=user_id, 
            is_active=True
        ).count()
        
        return jsonify(stats)
    except Exception as e:
        print(f"Ошибка API stats: {e}")
        return jsonify({'error': str(e)}), 500
    
@api_bp.route('/vk/stats/<int:account_id>')
def api_vk_stats(account_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authorized'}), 401
    
    account = VKAccount.query.filter_by(id=account_id, user_id=session['user_id']).first()
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # 1. Пытаемся взять реальную статистику из таблицы VKStatistic
    # Используем created_at вместо date или updated_at
    stats = VKStatistic.query.filter_by(vk_account_id=account_id).order_by(desc(VKStatistic.created_at)).first()
    
    # 2. Если в таблице статистики пусто, считаем "на лету" по постам из базы
    if not stats:
        posts_agg = db.session.query(
            func.sum(Post.likes).label('likes'),
            func.sum(Post.views).label('views'),
            func.sum(Post.comments).label('comments')
        ).filter(Post.vk_account_id == account_id).first()
        
        return jsonify({
            'stats': {
                'reach': (posts_agg.views or 0) * 1.2, # Примерный охват
                'engagement': (posts_agg.likes or 0) + (posts_agg.comments or 0),
                'likes': posts_agg.likes or 0,
                'views': posts_agg.views or 0,
                'created_at': datetime.now().isoformat()
            }
        })

    return jsonify({
        'stats': {
            'followers_count': stats.followers_count,
            'reach': stats.reach,
            'engagement': stats.engagement,
            'likes': stats.likes,
            'views': stats.views,
            'male_percentage': stats.male_percentage,
            'female_percentage': stats.female_percentage,
            'created_at': stats.created_at.isoformat() if stats.created_at else None
        }
    })

@api_bp.route('/vk/chart/<int:account_id>')
def api_vk_chart(account_id):
    """Берет реальные данные для графика из базы"""
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401

    # Вместо random используем функцию из сервиса
    growth_data = get_growth_data(session['user_id'])
    
    labels = [d.date.strftime('%d.%m') if hasattr(d.date, 'strftime') else str(d.date) for d in growth_data]
    reach_data = [d.views for d in growth_data]
    
    return jsonify({
        'chart_data': {
            'reach': {
                'labels': labels,
                'data': reach_data
            },
            'activity': {
                'labels': ['Лайки', 'Комменты', 'Репосты'],
                'data': [
                    db.session.query(func.sum(Post.likes)).filter_by(vk_account_id=account_id).scalar() or 0,
                    db.session.query(func.sum(Post.comments)).filter_by(vk_account_id=account_id).scalar() or 0,
                    db.session.query(func.sum(Post.shares)).filter_by(vk_account_id=account_id).scalar() or 0
                ]
            }
        }
    })

