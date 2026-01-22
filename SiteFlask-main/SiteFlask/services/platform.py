from datetime import datetime
from typing import Dict, List
import json

from modules.ai_moderator import AIContentModerator
from modules.ai_scheduler import AIContentScheduler
from models import db, Post, ModerationLog # Ваши модели
from utils.logger import get_logger

logger = get_logger(__name__)

class ContentPlatform:
    """
    Центральный класс управления контентом.
    Объединяет Модератора, Планировщик и Базу Данных.
    """
    
    def __init__(self, business_info: Dict):
        self.business_info = business_info
        self.moderator = AIContentModerator(business_info)
        self.scheduler = AIContentScheduler(business_info)
        # В Flask SQLAlchemy сессия глобальная (db.session), поэтому нам не нужно создавать новую
    
    def process_generated_content(self, content_list: List[Dict]) -> Dict:
        """
        Полный цикл: Модерация -> Планирование -> Сохранение
        """
        logger.info(f"🚀 Платформа начала обработку {len(content_list)} постов")
        
        approved_content = []
        rejected_content = []
        
        # --- ЭТАП 1: МОДЕРАЦИЯ ---
        for content in content_list:
            # Превращаем объект контента в словарь для удобства, если это еще не он
            moderation_result = self.moderator.moderate_content(content)
            
            # Логируем результат в БД (для админки)
            self._save_moderation_log(content, moderation_result)
            
            if moderation_result.passed:
                approved_content.append(content)
                self.moderator.add_to_published(content)
                logger.info(f"✅ Контент одобрен: {content.get('title')}")
            else:
                rejected_content.append({
                    'title': content.get('title'),
                    'issues': moderation_result.issues
                })
                logger.warning(f"❌ Контент отклонен: {content.get('title')}")

        # --- ЭТАП 2: ПЛАНИРОВАНИЕ ---
        scheduled_posts = []
        if approved_content:
            # Планируем, начиная с "завтра 9 утра" или следующего свободного слота
            current_time = datetime.now()
            
            # Вызываем умный планировщик
            scheduled_posts = self.scheduler.create_posting_schedule(
                content_list=approved_content,
                start_date=current_time 
            )
            print(scheduled_posts)
            
            # Сохраняем запланированное в БД
            for post in scheduled_posts:
                self._save_scheduled_post_to_db(post)
                
        # Формируем красивый отчет для frontend
        return {
            'success': True,
            'total': len(content_list),
            'approved_count': len(approved_content),
            'rejected_count': len(rejected_content),
            'scheduled_count': len(scheduled_posts),
            'rejected_details': rejected_content,
            'schedule_preview': [
                {
                    'title': p.content.get('title'),
                    'time': p.scheduled_time.strftime('%Y-%m-%d %H:%M'),
                    'platform': p.platforms[0]
                } for p in scheduled_posts
            ]
        }

    def _save_moderation_log(self, content: Dict, result):
        """Сохранение лога проверки в БД"""
        try:
            log = ModerationLog(
                business_id=self.business_info.get('id', 0), # Или user_id
                post_title=content.get('title', 'No Title'),
                passed=result.passed,
                score=result.score,
                issues=json.dumps(result.issues, ensure_ascii=False),
                suggestions=json.dumps(result.suggestions, ensure_ascii=False),
                created_at=datetime.utcnow()
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения лога модерации: {e}")
            db.session.rollback()

    def _save_scheduled_post_to_db(self, sched_post):
        try:
            new_post = Post(
                user_id=self.business_info.get('user_id'),
                vk_account_id=self.business_info.get('vk_account_id'),
                title=sched_post.content.get('title'),
                text=sched_post.content.get('text')[:2000], # VK лимит
                publish_date=sched_post.scheduled_time,
                
                # ИЗМЕНЕНИЕ ЗДЕСЬ:
                status='draft',      # Ставим статус "черновик"
                is_published=False,  # Еще не опубликован
                
                vk_post_id=None,     # ID от VK пока нет
                image_url=sched_post.content.get('image_url')
            )
            db.session.add(new_post)
            db.session.commit()
            return new_post
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            db.session.rollback()
    
    def auto_replenish_queue(self, count_to_generate=5):
        """
        Метод для Демона: Полная имитация логики vk_service.
        Генерация -> Модерация -> Картинка -> Планирование.
        """
        from services.ai_service import ai_service
        
        logger.info(f"🔄 [Auto-Replenish] Запуск полного цикла для {count_to_generate} постов...")
        
        # 1. Генерация идей
        strategy = self.business_info.get('description', '')
        themes = ai_service.generate_theme_ideas(self.business_info.get('user_id'), strategy)
        
        if not themes:
            logger.error("AI не вернул идей для постов")
            return 0

        generated_content_list = []

        # 2. Цикл генерации и модерации (как в vk_service)
        for theme in themes:
            if len(generated_content_list) >= count_to_generate:
                break

            # Генерация текста
            message = ai_service.generate_post_content(theme)
            
            content_to_moderate = {
                'title': theme,
                'text': message,
                'topic': theme
            }
            
            # --- МОДЕРАЦИЯ ---
            mod_result = self.moderator.moderate_content(content_to_moderate)
            if not mod_result.passed:
                logger.warning(f"Пост '{theme}' отклонен модератором: {mod_result.issues}")
                continue 

            # --- ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ ---
            image_url = None
            try:
                img_prompt = ai_service.generate_image_prompt(theme)
                if img_prompt:
                    image_url = ai_service.generate_image_url(img_prompt)
            except Exception as e:
                logger.error(f"Ошибка Image AI для '{theme}': {e}")

            generated_content_list.append({
                'title': theme,
                'text': message,
                'image_url': image_url,
                'content_type': 'post'
            })

        if not generated_content_list:
            logger.warning("Ни один пост не прошел модерацию.")
            return 0

        # 3. ПЛАНИРОВАНИЕ (AI Scheduler)
        # Находим точку старта (последний запланированный пост)
        last_post = Post.query.filter_by(
            vk_account_id=self.business_info['vk_account_id'], 
            status='scheduled'
        ).order_by(Post.publish_date.desc()).first()
        
        start_date = last_post.publish_date if last_post else datetime.now()

        scheduled_posts = self.scheduler.create_posting_schedule(
            content_list=generated_content_list,
            start_date=start_date
        )

        # 4. СОХРАНЕНИЕ В БД
        count = 0
        for s_post in scheduled_posts:
            try:
                new_post = Post(
                    user_id=self.business_info.get('user_id'),
                    vk_account_id=self.business_info.get('vk_account_id'),
                    title=s_post.content['title'],
                    text=s_post.content['text'][:2000],
                    publish_date=s_post.scheduled_time,
                    status='draft', 
                    is_published=False,
                    vk_post_id=f"temp_{s_post.id}",
                    image_url=s_post.content.get('image_url')
                )
                db.session.add(new_post)
                count += 1
            except Exception as e:
                logger.error(f"Ошибка сохранения: {e}")
        
        db.session.commit()
        logger.info(f"✅ Успешно добавлено {count} постов в очередь.")
        return count