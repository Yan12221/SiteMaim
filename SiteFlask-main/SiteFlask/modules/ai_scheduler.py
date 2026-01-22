from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from openai import OpenAI 
import json
import uuid

from config.settings import ai_config
from utils.logger import get_logger
from modules.social_api import SocialMediaPublisher

logger = get_logger(__name__)
client = OpenAI(api_key=ai_config.OPENAI_API_KEY)

@dataclass
class ScheduledPost:
    id: str
    content: Dict
    scheduled_time: datetime
    platforms: List[str]
    status: str = "scheduled"

class AIContentScheduler:
    def __init__(self, business_info: Dict):
        self.business_info = business_info
        self.scheduler = BackgroundScheduler()
        self.publisher = SocialMediaPublisher()
        self.scheduled_posts = {}
        self.scheduler.start()

    def create_posting_schedule(self, content_list: List[Dict], start_date=None) -> List[ScheduledPost]:
        if not start_date:
            start_date = datetime.now()
            
        # Спрашиваем у AI лучшее время
        best_times = self._get_best_posting_times()
        
        scheduled_result = []
        current_date = start_date

        for i, content in enumerate(content_list):
            # Берем время из списка лучших (циклично)
            time_str = best_times[i % len(best_times)]
            hour, minute = map(int, time_str.split(':'))
            
            # Собираем дату
            post_date = current_date.replace(hour=hour, minute=minute, second=0)
            
            # Если время уже прошло сегодня, переносим на завтра
            if post_date < datetime.now():
                post_date += timedelta(days=1)
                current_date += timedelta(days=1) # Сдвигаем текущий день тоже
            
            platforms = self._select_platforms(content)
            
            # Создаем объект
            post = ScheduledPost(
                id=f"post_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
                content=content,
                scheduled_time=post_date,
                platforms=platforms
            )
            
            # 1. Сохраняем в память планировщика
            self.scheduled_posts[post.id] = post
            
            # 2. Добавляем задачу в APScheduler
            self.scheduler.add_job(
                self._publish_post_wrapper,
                trigger=DateTrigger(run_date=post.scheduled_time),
                args=[post.id],
                id=post.id
            )
            
            # 3. ВАЖНО: Сохраняем в БД со статусом scheduled, чтобы работал счетчик
            self._save_temp_post_to_db(post)
            
            scheduled_result.append(post)
            
            # Следующий пост на следующий день
            current_date += timedelta(days=1)

        return scheduled_result
    #Github ругается
    def _get_best_posting_times(self) -> List[str]:
        """AI определяет лучшее время для постинга"""
        prompt = f"""
        Бизнес: {self.business_info.get('business_type')}.
        Предложи 3 лучших времени для постинга (формат HH:MM).
        Верни JSON: {{ "times": ["09:00", "18:00", "21:00"] }}
        """
        try:
            response = client.chat.completions.create(
                model=ai_config.MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            times = data.get('times')
            if isinstance(times, list) and len(times) > 0:
                return times
            return ["10:00", "19:00"] # Запасной вариант, если список пустой
        except Exception as e:
            logger.error(f"Ошибка получения времени от AI: {e}")
            return ["09:00", "12:00", "18:00"] # Фолбек при любой ошибке

    def _select_platforms(self, content: Dict) -> List[str]:
        # Пока просто возвращаем доступные, можно усложнить через AI
        return self.business_info.get('connected_platforms', ['vk'])
    
    def _publish_post_wrapper(self, post_id: str):
        """Публикация поста (вызывается планировщиком)"""
        # --- ИМПОРТ МОДЕЛЕЙ ВНУТРИ ФУНКЦИИ (чтобы избежать циклических импортов) ---
        from models import db, Post
        # ---------------------------------------------------------------------------

        post = self.scheduled_posts.get(post_id)
        if not post:
            logger.error(f"Пост {post_id} не найден в памяти планировщика")
            return
        
        logger.info(f"Начало публикации поста: {post.content.get('title')}")
        
        success = True
        published_vk_id = None
        
        # --- 1. ПУБЛИКАЦИЯ В СОЦСЕТИ ---
        for platform in post.platforms:
            try:
                result = self.publisher.publish(
                    platform=platform,
                    content=post.content,
                    business_info=self.business_info
                )
                
                if not result['success']:
                    success = False
                    logger.error(f"Ошибка: {result.get('error')}")
                else:
                    # Если это VK, запоминаем ID поста
                    if platform == 'vk':
                        published_vk_id = result.get('post_id')
                    logger.info(f"✅ Успешно опубликовано в {platform}")
                    
            except Exception as e:
                logger.error(f"Исключение: {e}")
                success = False
        
        # --- 2. ОБНОВЛЕНИЕ СТАТУСА В БАЗЕ ДАННЫХ ---
        remaining_posts_count = 0 
        try:
            # Ищем пост в БД по временному ID (vk_post_id = temp_...)
            db_post = Post.query.filter_by(vk_post_id=f"temp_{post.id}").first()
            
            if db_post:
                if success:
                    db_post.status = 'published'
                    db_post.is_published = True
                    db_post.published_time = datetime.now()
                    if published_vk_id:
                        # Обновляем реальный ID поста из VK
                        db_post.vk_post_id = f"-{self.business_info['vk_group_id']}_{published_vk_id}"
                else:
                    db_post.status = 'failed'
                
                db.session.commit()
                logger.info(f"Статус поста в БД обновлен на {db_post.status}")
            
            # Подсчет оставшихся постов
            remaining_posts_count = Post.query.filter(Post.status.in_(['scheduled', 'draft'])).count()
            logger.info(f"📉 В очереди осталось постов: {remaining_posts_count}")
            
        except Exception as e:
            logger.error(f"Не удалось обновить статус в БД: {e}")
            db.session.rollback()
            
        if success:
            post.status = "published"
        else:
            post.status = "failed"

        # --- 3. АВТОПОПОЛНЕНИЕ ОЧЕРЕДИ ---
        # Если постов осталось 0 (или меньше), запускаем генерацию новых
        if success and remaining_posts_count == 0:
            logger.info("🪫 Очередь пуста! Запускаю автогенерацию 5 новых постов...")
            self._auto_refill_queue(count=5)

    def _auto_refill_queue(self, count=5):
        """Автоматическая генерация и добавление постов в расписание"""
        try:
            # 1. Генерируем контент через AI
            new_content_list = self._generate_content_via_ai(count)
            
            if not new_content_list:
                logger.warning("AI не вернул контент для автопополнения.")
                return

            # 2. Определяем дату начала (завтра)
            start_date = datetime.now() + timedelta(days=1)
            
            # 3. Планируем
            logger.info(f"Планирую {len(new_content_list)} новых постов...")
            scheduled = self.create_posting_schedule(new_content_list, start_date=start_date)
            logger.info(f"✅ Успешно запланировано {len(scheduled)} постов (автопополнение).")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при автопополнении очереди: {e}")

    def _generate_content_via_ai(self, count: int) -> List[Dict]:
        """Генерация контента (текста) через AI для автопополнения"""
        logger.info("Запрос к OpenAI для генерации контента...")
        prompt = f"""
        Ты SMM-менеджер. Тема бизнеса: {self.business_info.get('business_type')}.
        Сгенерируй {count} уникальных идей для постов.
        Формат ответа JSON:
        {{
            "posts": [
                {{
                    "title": "Краткий заголовок",
                    "body": "Текст поста с эмодзи"
                }}
            ]
        }}
        """
        try:
            response = client.chat.completions.create(
                model=ai_config.MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            posts = data.get('posts', [])
            return posts
        except Exception as e:
            logger.error(f"Ошибка генерации контента: {e}")
            return []

    def _save_temp_post_to_db(self, post: ScheduledPost):
        """Сохранение черновика в БД для учета очереди"""
        from models import db, Post
        try:
            new_db_post = Post(
                title=post.content.get('title', 'Auto Generated'),
                body=post.content.get('body', ''),
                status='scheduled',
                vk_post_id=f"temp_{post.id}", # Временный маркер для связки
                scheduled_time=post.scheduled_time,
                is_published=False
            )
            db.session.add(new_db_post)
            db.session.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения черновика в БД: {e}")
            db.session.rollback()

    def _select_platforms(self, content: Dict) -> List[str]:
        # Пока просто возвращаем доступные
        return self.business_info.get('connected_platforms', ['vk'])
    
    def cancel_post(self, post_id: str) -> bool:
        """Отмена запланированного поста"""
        from models import db, Post # Для обновления БД при отмене
        
        post = self.scheduled_posts.get(post_id)
        
        if not post:
            logger.warning(f"Пост {post_id} не найден")
            return False
        
        if post.status != "scheduled":
            logger.warning(f"Невозможно отменить пост {post_id} со статусом {post.status}")
            return False
        
        try:
            # Удаляем задачу из планировщика
            self.scheduler.remove_job(post.id)
            post.status = "cancelled"
            
            # Обновляем в БД
            db_post = Post.query.filter_by(vk_post_id=f"temp_{post.id}").first()
            if db_post:
                db_post.status = 'cancelled'
                db.session.commit()
                
            logger.info(f"Пост {post_id} отменен")
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены поста: {e}")
            return False
    
    def reschedule_post(self, post_id: str, new_datetime: datetime) -> bool:
        """Перенос публикации на другое время"""
        from models import db, Post

        post = self.scheduled_posts.get(post_id)
        if not post:
            return False
        
        try:
            self.scheduler.reschedule_job(post.id, trigger=DateTrigger(run_date=new_datetime))
            post.scheduled_time = new_datetime
            
            # Обновляем в БД
            db_post = Post.query.filter_by(vk_post_id=f"temp_{post.id}").first()
            if db_post:
                db_post.scheduled_time = new_datetime
                db.session.commit()
                
            logger.info(f"Пост {post_id} перенесен на {new_datetime.strftime('%Y-%m-%d %H:%M')}")
            return True
        except Exception as e:
            logger.error(f"Ошибка переноса: {e}")
            return False
    
    def get_calendar(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Получение календаря публикаций"""
        calendar = []
        for post in self.scheduled_posts.values():
            if start_date <= post.scheduled_time <= end_date:
                calendar.append({
                    'id': post.id,
                    'title': post.content.get('title', 'Без заголовка'),
                    'scheduled_time': post.scheduled_time.isoformat(),
                    'platforms': post.platforms,
                    'status': post.status
                })
        calendar.sort(key=lambda x: x['scheduled_time'])
        return calendar
    
    def shutdown(self):
        """Корректное завершение работы планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")
