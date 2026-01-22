import time
import pytz
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
# --- ИМПОРТЫ ---
from app import app, db 
from models import Post as DBScheduledPost, VKAccount, BusinessProfile # Добавили VKAccount
from services.platform import ContentPlatform # Импорт платформы
from utils.logger import get_logger



logger = get_logger("AutoPublisherDaemon")

class PublisherDaemon:
    def __init__(self):
        # Планировщик инициализируем позже, внутри цикла обработки аккаунтов,
        # или используем глобальный, если он один на всех.
        # Для простоты создадим временный экземпляр платформы для доступа к шедулеру
        # Но лучше хранить шедулеры отдельно.
        # В данном решении мы будем создавать Platform на лету.
        pass

    def check_and_refill_queues(self):
        """
        Проверяет все активные аккаунты. Если постов мало -> генерирует новые.
        """
        logger.info("🔍 Проверка очередей постов для всех аккаунтов...")
        
        with app.app_context():
            # Получаем все активные VK аккаунты
            active_accounts = VKAccount.query.filter_by(is_active=True).all()
            
            for account in active_accounts:
                # Считаем, сколько постов запланировано в будущем
                pending_count = DBScheduledPost.query.filter_by(
                    vk_account_id=account.id, 
                    status='scheduled'
                ).count()
                
                for account in active_accounts:
                    # ИЗМЕНЕНИЕ: Считаем и запланированные, и черновики
                    pending_count = DBScheduledPost.query.filter(
                        DBScheduledPost.vk_account_id == account.id,
                        DBScheduledPost.status.in_(['scheduled', 'draft']) # Учитываем оба статуса
                    ).count()
                    
                    logger.info(f"Аккаунт {account.group_name}: в очереди {pending_count} постов (включая черновики).")
                # ЕСЛИ ПОСТОВ МАЛО (например, меньше 2) -> ГЕНЕРИРУЕМ ЕЩЕ 5
                if pending_count == 0:
                    logger.info(f"⚡ Очередь пуста! Запускаю автогенерацию для {account.group_name}...")
                    
                    # Собираем business_info для платформы
                    profile = BusinessProfile.query.filter_by(user_id=account.user_id).first()
                    if not profile:
                        continue
                        
                    business_info = {
                        'user_id': account.user_id,
                        'vk_account_id': account.id,
                        'vk_group_id': account.group_id,
                        'access_token': account.access_token,
                        'description': profile.description,
                        'business_type': profile.niche,
                        # ... остальные поля по необходимости
                        'connected_platforms': ['vk']
                    }
                    
                    # Создаем платформу и запускаем генерацию
                    platform = ContentPlatform(business_info)
                    platform.auto_replenish_queue(count_to_generate=5)
                    
                    # После генерации нужно обновить задачи в памяти (перезагрузить шедулер)
                    self.restore_schedule_for_account(account.id, platform.scheduler)

    def restore_schedule_for_account(self, account_id, scheduler_instance):
        """
        Загружает задачи из БД в память планировщика конкретной платформы
        """
        pending_posts = DBScheduledPost.query.filter_by(
            vk_account_id=account_id, 
            status='scheduled'
        ).all()
        
        timezone = pytz.timezone('Europe/Moscow')
        now = datetime.now(timezone)
        
        for db_post in pending_posts:
            # Если задача уже есть в планировщике, пропускаем (или обновляем)
            # Для простоты - добавляем через try/except
            
            if db_post.publish_date.tzinfo is None:
                post_time = timezone.localize(db_post.publish_date)
            else:
                post_time = db_post.publish_date
                
            # Проверка на просрочку
            run_date = post_time if post_time > now else datetime.now(timezone) + timedelta(seconds=10)

            try:
                scheduler_instance.scheduler.add_job(
                    func=self._publish_wrapper,
                    trigger=DateTrigger(run_date=run_date),
                    args=[db_post.id, scheduler_instance], # Передаем ID и экземпляр шедулера
                    id=str(db_post.id),
                    replace_existing=True
                )
            except Exception:
                pass # Задача уже есть или ошибка

    def _publish_wrapper(self, db_post_id: int, scheduler_instance):
        """
        Обертка публикации. Находит пост в БД и отправляет.
        """
        with app.app_context():
            logger.info(f"🚀 Публикация поста ID {db_post_id}...")
            
            db_post = DBScheduledPost.query.get(db_post_id)
            if not db_post or db_post.status != 'scheduled':
                return

            # Формируем контент для паблишера
            from modules.social_api import SocialMediaPublisher
            publisher = SocialMediaPublisher()
            
            # Находим аккаунт для токена
            account = VKAccount.query.get(db_post.vk_account_id)
            business_info = {
                'vk_group_id': account.group_id,
                'access_token': account.access_token
            }
            
            content = {
                'title': db_post.title,
                'text': db_post.text,
                'image_url': db_post.image_url
            }

            # Публикуем
            res = publisher.publish('vk', content, business_info)
            
            if res['success']:
                db_post.status = 'published'
                db_post.is_published = True
                db_post.vk_post_id = str(res.get('post_id'))
                logger.info(f"✅ Успешно опубликовано! VK ID: {res.get('post_id')}")
            else:
                db_post.status = 'failed'
                logger.error(f"❌ Ошибка публикации: {res.get('error')}")
            
            db.session.commit()

    def run_forever(self):
        logger.info("🏁 SUPER-DAEMON запущен! (Мониторинг + Автопостинг)")
        
        # Основной цикл
        while True:
            try:
                # 1. Проверяем, нужно ли создать новые посты
                self.check_and_refill_queues()
                
                # 2. Здесь мы должны дать поработать планировщикам. 
                # Но так как мы создаем экземпляры scheduler динамически, 
                # лучше использовать глобальный подход.
                # В упрощенном варианте: check_and_refill_queues наполнит БД,
                # а отдельный поток должен эти задачи исполнять.
                
                # ДЛЯ СТАБИЛЬНОСТИ: 
                # Сейчас самый надежный вариант - этот скрипт занимается ГЕНЕРАЦИЕЙ,
                # а исполнение задач (APScheduler) лучше держать внутри app.py или 
                # вызывать здесь restore_schedule_from_db глобально.
                
                self.process_due_posts() # См. метод ниже
                
                logger.info("💤 Сплю 60 секунд перед следующей проверкой...")
                time.sleep(60) 
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Глобальная ошибка демона: {e}")
                time.sleep(10)

    def process_due_posts(self):
        """
        Простой поллинг базы вместо сложного APScheduler в памяти.
        Берет посты, у которых время пришло, и публикует их.
        """
        with app.app_context():
            timezone = pytz.timezone('Europe/Moscow')
            now = datetime.now(timezone)
            
            # Ищем посты, которые 'scheduled' и время уже наступило (или прошло)
            due_posts = DBScheduledPost.query.filter(
                DBScheduledPost.status == 'scheduled',
                DBScheduledPost.publish_date <= now.replace(tzinfo=None) # Сравниваем без tz если в базе naive
            ).all()
            
            for post in due_posts:
                # Чтобы не создать дубли, можно использовать фиктивный scheduler_instance или None
                self._publish_wrapper(post.id, None)

if __name__ == "__main__":
    daemon = PublisherDaemon()
    daemon.run_forever()