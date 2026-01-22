from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Any

from modules.ai_moderator import AIContentModerator
from modules.ai_scheduler import AIContentScheduler
from models import Session, ScheduledPost as DBScheduledPost, ModerationLog
from utils.logger import get_logger

logger = get_logger(__name__)

class ContentPlatform:
    """Главный класс платформы"""
    
    def __init__(self, business_info: Dict):
        self.business_info = business_info
        self.moderator = AIContentModerator(business_info)
        self.scheduler = AIContentScheduler(business_info)
        self.db_session = Session()
    
    def process_generated_content(
        self,
        content_list: List[Dict],
        auto_publish: bool = False
    ) -> Dict:
        """
        Обработка сгенерированного контента
        """
        logger.info(f"Начало обработки {len(content_list)} постов")
        
        approved_content = []
        rejected_content = []
        
        # Этап 1: Модерация
        for content in content_list:
            logger.info(f"Модерация: {content.get('title', 'Без заголовка')}")
            
            moderation_result = self.moderator.moderate_content(content)
            
            # Сохраняем лог модерации
            self._save_moderation_log(content, moderation_result)
            
            if moderation_result.passed:
                approved_content.append(content)
                self.moderator.add_to_published(content)
                logger.info(f"✅ Контент одобрен")
            else:
                rejected_content.append({
                    'content': content,
                    'moderation_result': moderation_result
                })
                logger.warning(f"❌ Контент отклонен")
                
                # Выводим отчет о модерации
                print(self.moderator.get_moderation_report(moderation_result))
        
        # Этап 2: Планирование одобренного контента
        scheduled_posts = []
        
        if approved_content:
            logger.info(f"Планирование {len(approved_content)} одобренных постов")
            
            scheduled_posts = self.scheduler.create_posting_schedule(
                content_list=approved_content,
                start_date=datetime.now(pytz.timezone('Europe/Moscow')) + timedelta(hours=1)
            )
            
            # Сохраняем в БД
            for post in scheduled_posts:
                self._save_scheduled_post(post)
        
        # Формируем результат
        result = {
            'total': len(content_list),
            'approved': len(approved_content),
            'rejected': len(rejected_content),
            'scheduled': len(scheduled_posts),
            'rejected_details': rejected_content,
            'schedule': [
                {
                    'id': p.id,
                    'title': p.content.get('title'),
                    'time': p.scheduled_time.strftime('%Y-%m-%d %H:%M'),
                    'platforms': p.platforms
                }
                for p in scheduled_posts
            ]
        }
        
        logger.info(
            f"Обработка завершена: {result['approved']}/{result['total']} одобрено, "
            f"{result['scheduled']} запланировано"
        )
        
        return result
    
    def _save_moderation_log(self, content: Dict, result):
        """Сохранение лога модерации в БД"""
        # Здесь content может тоже содержать даты, лучше обезопасить
        safe_content = self._prepare_for_json(content)
        
        log = ModerationLog(
            post_id=safe_content.get('id', 'unknown'),
            business_id=self.business_info.get('id', 'unknown'),
            passed=1 if result.passed else 0,
            score=result.score,
            issues=self._prepare_for_json(result.issues), # Тоже чистим на всякий случай
            suggestions=self._prepare_for_json(result.suggestions),
            check_details=self._prepare_for_json(result.check_details)
        )
        self.db_session.add(log)
        self.db_session.commit()

    def _prepare_for_json(self, data: Any) -> Any:
        """
        Рекурсивно преобразует объекты datetime в строки для сохранения в JSON поле БД.
        Исправляет ошибку: TypeError: Object of type datetime is not JSON serializable
        """
        if isinstance(data, dict):
            return {k: self._prepare_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(v) for v in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data
    
    def _save_scheduled_post(self, post):
        """Сохранение запланированного поста в БД"""
        
        # ВАЖНО: Преобразуем контент, убирая объекты datetime внутри словаря
        safe_content = self._prepare_for_json(post.content)

        db_post = DBScheduledPost(
            id=post.id,
            business_id=self.business_info.get('id', 'unknown'),
            content=safe_content,  # Используем подготовленный словарь
            scheduled_time=post.scheduled_time, # Здесь оставляем datetime (SQLAlchemy умеет писать в колонку DateTime)
            platforms=post.platforms,
            status=post.status
        )
        self.db_session.add(db_post)
        self.db_session.commit()
    
    def get_calendar(self, days: int = 30) -> List[Dict]:
        """Получение календаря публикаций"""
        start_date = datetime.now(pytz.timezone('Europe/Moscow'))
        end_date = start_date + timedelta(days=days)
        
        return self.scheduler.get_calendar(start_date, end_date)
    
    def cancel_post(self, post_id: str) -> bool:
        """Отмена публикации"""
        success = self.scheduler.cancel_post(post_id)
        
        if success:
            # Обновляем в БД
            post = self.db_session.query(DBScheduledPost).filter_by(id=post_id).first()
            if post:
                post.status = 'cancelled'
                self.db_session.commit()
        
        return success

# Пример использования
if __name__ == "__main__":
    # Информация о бизнесе
    business_info = {
        'id': 'business_123',
        'business_type': 'Кофейня',
        'description': 'Уютная кофейня в центре города',
        'target_audience': 'Молодежь 18-35 лет, любители кофе',
        'brand_values': ['качество', 'уют', 'дружелюбие'],
        'topics': ['кофе', 'десерты', 'атмосфера', 'события'],
        'stop_words': ['дешево', 'акция', 'скидка'],
        'connected_platforms': ['vk', 'telegram'],
        'vk_group_id': '123456789',
        'telegram_channel_id': '@my_coffee_shop'
    }
    
    # Пример сгенерированного контента
    generated_content = [
        {
            'id': 'post_001',
            'title': '☕ BMW продажа',
            'text': 'Встречайте новинку! Мы привезли удивительный сорт арабики из Эфиопии. '
                    'Этот кофе обладает ярким фруктовым вкусом с нотками черники и цитрусов. '
                    'Приходите попробовать!',
            'topic': 'кофе',
            'content_type': 'announcement'
        },
        {
            'id': 'post_002',
            'title': '🎉 Дешевая акция на все позиции!',
            'text': 'Успейте купить кофе по сниженным ценам! Дешево!',
            'topic': 'акция',
            'content_type': 'promo'
        },
        {
            'id': 'post_003',
            'title': '🍰 Домашние десерты каждый день',
            'text': 'Наши кондитеры готовят свежие десерты каждое утро. '
                    'Чизкейки, тирамису, брауни - все это прекрасно сочетается с нашим кофе. '
                    'Заходите на чашечку кофе и сладость!',
            'topic': 'десерты',
            'content_type': 'product'
        }
    ]
    
    # Инициализация платформы
    platform = ContentPlatform(business_info)
    
    # Обработка контента
    result = platform.process_generated_content(generated_content)
    
    # Вывод результатов
    print("\n" + "="*60)
    print("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ КОНТЕНТА")
    print("="*60)
    print(f"Всего постов: {result['total']}")
    print(f"✅ Одобрено: {result['approved']}")
    print(f"❌ Отклонено: {result['rejected']}")
    print(f"📅 Запланировано: {result['scheduled']}")
    
    print("\n📅 РАСПИСАНИЕ ПУБЛИКАЦИЙ:")
    print("-"*60)
    for item in result['schedule']:
        print(f"{item['time']} | {item['title']}")
        print(f"  Платформы: {', '.join(item['platforms'])}")
        print()
    
    # Получение календаря
    calendar = platform.get_calendar(days=7)
    print("\n📆 КАЛЕНДАРЬ НА 7 ДНЕЙ:")
    print("-"*60)
    for event in calendar:
        print(f"{event['scheduled_time']} - {event['title']} ({event['status']})")