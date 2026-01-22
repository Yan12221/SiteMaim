from flask import Blueprint, request, jsonify, session
from models import VKAccount, Post, db, BusinessProfile


# Импорт новых компонентов
from services.ai_service import ai_service
from modules.ai_scheduler import AIContentScheduler
from modules.ai_moderator import AIContentModerator
from utils.logger import get_logger

logger = get_logger(__name__)
vk_bp = Blueprint('vk', __name__)

@vk_bp.route('/api/vk/auto-generate-posts', methods=['POST'])
def api_vk_auto_generate():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Не авторизован'}), 401

        data = request.get_json()
        user_id = session['user_id']
        vk_account_id = data.get('vk_account_id')
        
        # 1. Получаем профиль бизнеса и аккаунт
        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        vk_account = VKAccount.query.filter_by(id=vk_account_id, user_id=user_id).first()
        
        if not profile or not vk_account:
            return jsonify({'success': False, 'error': 'Профиль или аккаунт не найден'}), 404

        # Подготовка данных для новых сервисов
        business_info = {
            'business_type': profile.niche,
            'target_audience': profile.target_audience,
            'description': profile.description,
            'stop_words': profile.stop_words.split(',') if profile.stop_words else [],
            'brand_values': [profile.goals], # Используем цели как ценности
            'topics': [profile.niche],
            'vk_group_id': vk_account.group_id,
            'connected_platforms': ['vk']
        }

        # Инициализация новых модулей
        moderator = AIContentModerator(business_info)
        scheduler = AIContentScheduler(business_info)

        # 2. Генерация идей (используем ваш старый метод как базовый генератор)
        strategy = profile.BusinessPrompt or profile.description
        themes = ai_service.generate_theme_ideas(user_id, strategy)
        
        generated_content_list = []

        # 3. Генерация контента и Модерация
        for theme in themes:
            # Генерация текста
            message = ai_service.generate_post_content(theme)
            
            # Подготовка объекта для модератора
            content_to_moderate = {
                'title': theme,
                'text': message,
                'topic': theme
            }
            
            # --- НОВАЯ МОДЕРАЦИЯ ---
            mod_result = moderator.moderate_content(content_to_moderate)
            print(mod_result)
            if not mod_result.passed:
                logger.warning(f"Пост '{theme}' не прошел модерацию: {mod_result.issues}")
                continue # Пропускаем плохой контент

            # Генерация изображения (если прошел модерацию)
            img_prompt = ai_service.generate_image_prompt(theme)
            
            image_url = None
            try:
                img_prompt = ai_service.generate_image_prompt(theme)
                if img_prompt:
                    image_url = ai_service.generate_image_url(img_prompt)
            except Exception as e:
                logger.error(f"Не удалось создать картинку для {theme}: {e}")

            generated_content_list.append({
                'title': theme,
                'text': message,
                'image_url': image_url, # Ссылка полетит в планировщик
                'content_type': 'post'
            })

        if not generated_content_list:
            return jsonify({'success': False, 'error': 'Контент не прошел модерацию'}), 400

        # 4. --- НОВОЕ ПЛАНИРОВАНИЕ (AI Scheduler) ---
        # Планировщик сам выберет лучшие времена и создаст задачи
        scheduled_posts = scheduler.create_posting_schedule(
            content_list=generated_content_list,
            posts_per_week=5
        )
        print(scheduled_posts)
        # 5. Сохранение в базу данных для отображения в интерфейсе
        for s_post in scheduled_posts:
            print(s_post)
            print(s_post.scheduled_time)
            new_post = Post(
                user_id=user_id,
                vk_account_id=vk_account.id,
                title=s_post.content['title'],
                text=s_post.content['text'][:500],
                publish_date=s_post.scheduled_time,
                status='scheduled', # Теперь статус "Запланирован"
                is_published=False,
                vk_post_id=f"temp_{s_post.id}" # Будет обновлен после реальной публикации
            )
            db.session.add(new_post)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'count': len(scheduled_posts),
            'message': 'Посты проверены AI и поставлены в очередь публикации'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка в автогенерации: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500