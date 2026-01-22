from flask import Blueprint, jsonify, render_template, request, session, redirect
from models import BusinessProfile, VKAccount, PostTheme, Post, User, db
import matplotlib
matplotlib.use('Agg')

from routes.dashboard_service import (
    get_overall_statistics,
    get_top_posts,
    get_growth_data,
    get_audience_data,
    generate_growth_chart,
    generate_audience_chart,
    generate_engagement_chart
)

unified_bp = Blueprint('unified', __name__)

@unified_bp.route('/api/calendar-posts')
def get_calendar_posts():
    if 'user_id' not in session:
        return jsonify([])
    
    user_id = session['user_id']
    # Важно: SQLAlchemy регистрозависим, убедись, что класс Post импортирован правильно
    posts = Post.query.filter_by(user_id=user_id).all()
    
    events = []
    for post in posts:
        # Проверка, чтобы не упасть, если publish_date вдруг None
        if post.publish_date:
            events.append({
                'id': post.id,
                'title': post.title or (post.text[:30] + "..."), 
                'start': post.publish_date.isoformat(), 
                'color': '#28a745' if post.is_published else '#ffc107',
                'allDay': False
            })
    
    return jsonify(events)

@unified_bp.route('/unified-dashboard')
def unified_dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    # Собираем статистику из всех источников
    overall_stats = get_overall_statistics(user_id)
    top_posts = get_top_posts(user_id)
    growth_data = get_growth_data(user_id)
    audience_data = get_audience_data(user_id)

    vk_account = VKAccount.query.filter_by(user_id=user_id, is_active=True).first()
    selected_account_id = vk_account.id if vk_account else None

    profile = BusinessProfile.query.filter_by(user_id=user_id).first()
    # Генерируем графики
    charts = {
        'growth_chart': generate_growth_chart(growth_data),
        'audience_chart': generate_audience_chart(audience_data),
        'engagement_chart': generate_engagement_chart(user_id)
    }

    user_themes = PostTheme.query.filter_by(user_id=user_id).order_by(PostTheme.created_at.desc()).all()

    return render_template('unified_dashboard.html',
                         stats=overall_stats,
                         top_posts=top_posts,
                         charts=charts,
                         profile=profile,
                         themes=user_themes,
                         selected_account_id=selected_account_id,
                         username=session.get('username'))

@unified_bp.route('/api/save-theme', methods=['POST'])
def save_theme():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    
    data = request.get_json()
    new_theme = data.get('theme') # 'dark' или 'light'
    
    user = User.query.get(session['user_id'])
    if user:
        user.theme_mode = new_theme
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 404