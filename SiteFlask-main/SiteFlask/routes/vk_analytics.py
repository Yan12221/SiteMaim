from flask import Blueprint, request, jsonify, session, render_template, redirect
from models import VKAccount, BusinessProfile, VKStatistic, db, Post
from services.ai_service import ai_service
from datetime import datetime
from models import Post
from modules.social_api import VKontakteAPI
import requests

vk_bp = Blueprint('vk', __name__)
platforms_cache = {} # Кэш платформ пользователей

@vk_bp.route('/api/vk/auto-generate-posts', methods=['POST'])
def api_vk_auto_generate():
    try:
        user_id = session.get('user_id')
        data = request.get_json() or {}
        vk_account_id = data.get('vk_account_id') # Проверьте, что JS это присылает!

        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        # Если vk_account_id не пришел, берем первый активный для этого юзера
        if not vk_account_id:
            vk_account = VKAccount.query.filter_by(user_id=user_id, is_active=True).first()
        else:
            vk_account = VKAccount.query.filter_by(id=vk_account_id, user_id=user_id).first()

        if not profile or not vk_account:
            return jsonify({'error': 'Настройте профиль бизнеса и подключите ВК'}), 400

        # Собираем данные
        business_info = {
            'id': profile.id,
            'user_id': user_id,
            'vk_account_id': vk_account.id,
            'business_type': profile.niche,
            'stop_words': profile.stop_words.split(',') if profile.stop_words else [],
            'topics': [profile.niche],
            'vk_group_id': vk_account.group_id,
            'access_token': vk_account.access_token
        }

        # Генерируем идеи
        themes = ai_service.generate_theme_ideas(user_id, profile.BusinessPrompt)
        
        raw_content_list = []
        for theme in themes:
            text = ai_service.generate_post_content(theme)
            # Если генерация упала, пропускаем или берем дефолт
            if text:
                raw_content_list.append({
                    'title': theme,
                    'text': text,
                    'image_url': None # Или вызовите генератор картинок
                })

        # ИСПРАВЛЕННЫЙ ИМПОРТ:
    
        from services.platform import ContentPlatform
        
        platform = ContentPlatform(business_info)
        result = platform.process_generated_content(raw_content_list)

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        print(f"❌ ERROR IN AUTO-GEN: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@vk_bp.route('/moderation')
def moderation_page():
    if 'user_id' not in session: return redirect('/login')
    
    # Берем посты со статусом 'draft'
    drafts = Post.query.filter_by(
        user_id=session['user_id'], 
        status='draft'
    ).order_by(Post.publish_date).all()
    
    return render_template('moderate.html', posts=drafts)

# 2. API Подтверждения (отправляет в VK)
@vk_bp.route('/api/approve-post/<int:post_id>', methods=['POST'])
def approve_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Находим токен доступа для этого поста
    vk_account = VKAccount.query.get(post.vk_account_id)
    if not vk_account:
        return jsonify({'success': False, 'error': 'Аккаунт VK не найден'})

    # Формируем данные для отправки
    # Мы используем ваш существующий social_api.py
    vk_api = VKontakteAPI()
    
    content_to_send = {
        'text': post.text,
        'image_url': post.image_url,
        # Если дата в будущем, VK сам поставит в очередь (отложка)
        'publish_date': int(post.publish_date.timestamp()) 
    }
    
    business_info = {
        'vk_group_id': vk_account.group_id,
        'access_token': vk_account.access_token
    }

    # ОТПРАВЛЯЕМ В VK
    result = vk_api.publish(content_to_send, business_info)

    if result.get('success'):
        # Если успешно — обновляем статус в нашей базе
        post.status = 'scheduled' if post.publish_date > datetime.now() else 'published'
        post.vk_post_id = str(result.get('post_id'))
        post.is_published = True
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': result.get('error')})

# 3. API Отклонения (Удаляет из базы)
@vk_bp.route('/api/reject-post/<int:post_id>', methods=['POST'])
def reject_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

@vk_bp.route('/api/vk/fetch/<int:account_id>', methods=['POST'])
def fetch_vk_data(account_id):
    user_id = session.get('user_id')
    account = VKAccount.query.filter_by(id=account_id, user_id=user_id).first()
    
    if not account:
        return jsonify({'success': False, 'error': 'Аккаунт не найден'})

    try:
        # --- ЧАСТЬ 1: Обновляем метрики постов (wall.get) ---
        wall_url = "https://api.vk.com/method/wall.get"
        wall_params = {
            'access_token': account.access_token,
            'v': '5.199',
            'owner_id': f"-{account.group_id}", # Минус для группы обязателен
            'count': 50, # Берем последние 50 постов
            'extended': 0
        }
        
        wall_res = requests.get(wall_url, params=wall_params).json()
        
        updated_count = 0
        if 'response' in wall_res:
            for item in wall_res['response']['items']:
                # Формируем ID в том формате, как он записан у вас в AI Scheduler
                # Формат: -GROUPID_POSTID (например: -12345678_154)
                full_vk_id = f"{item['owner_id']}_{item['id']}"
                
                # Ищем пост в нашей базе
                post = Post.query.filter_by(vk_post_id=full_vk_id).first()
                
                if post:
                    # Обновляем цифры
                    post.likes = item.get('likes', {}).get('count', 0)
                    post.views = item.get('views', {}).get('count', 0)
                    post.shares = item.get('reposts', {}).get('count', 0)
                    post.comments = item.get('comments', {}).get('count', 0)
                    updated_count += 1
        
        # --- ЧАСТЬ 2: Обновляем общую статистику группы (stats.get) ---
        stats_url = "https://api.vk.com/method/stats.get"
        stats_params = {
            'access_token': account.access_token,
            'v': '5.199',
            'group_id': account.group_id,
            'interval': 'day',
            'intervals_count': 1
        }
        
        stats_res = requests.get(stats_url, params=stats_params).json()
        
        if 'response' in stats_res and stats_res['response']:
            data = stats_res['response'][0]
            
            stat_record = VKStatistic.query.filter_by(vk_account_id=account.id).first()
            if not stat_record:
                stat_record = VKStatistic(vk_account_id=account.id)
                db.session.add(stat_record)
            
            # Обновляем поля статистики
            stat_record.reach = data.get('reach', {}).get('reach', 0)
            stat_record.engagement = data.get('visitors', {}).get('views', 0)
            stat_record.updated_at = datetime.now() # Или created_at, как у вас в модели
            
            # Демография (если нужно)
            if 'sex' in data.get('reach', {}):
                sex_data = data['reach']['sex']
                # Простая логика: ищем процент женщин (f) и мужчин (m)
                # ... тут можно добавить парсинг пола ...

        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'Обновлено постов: {updated_count}, статистика загружена.'
        })

    except Exception as e:
        print(f"Ошибка обновления VK: {e}")
        return jsonify({'success': False, 'error': str(e)})