# test_daemon.py
from app import app, db
from models import Post, VKAccount, BusinessProfile
from datetime import datetime, timedelta

def setup_test_environment():
    with app.app_context():
        # 1. Проверяем наличие тестового пользователя (user_id=1)
        # Если у тебя другой ID, поменяй здесь
        user_id = 1 

        # 2. Создаем или находим VK Аккаунт
        account = VKAccount.query.filter_by(user_id=user_id).first()
        
        if not account:
            print("Adding new test VK account...")
            account = VKAccount(
                user_id=user_id,
                group_id="234648612", # Тестовый ID группы
                group_name="Тестовое Сообщество",
                # ВАЖНО: поставь здесь свой реальный токен, если хочешь, 
                # чтобы демон реально опубликовал пост в ВК
                access_token="vk1.a.djhd3Ex7pvSIMG4ZDNaZ424QFv11X7JrR0qtrfd263fphe3RDr59rBcOqsUMDVxPpuma5JKAbKyx5vAXNtHBS0kDWZXvfaR7ZVkQxL-eAUiBbg5ona2HjaE6MY2e6-XTxGLJ56stSIm6qu0wWkrQwweTuBdQuF8jBNtr7ZmQ80XDQtPYqiTUPo9I2JIvx76z", 
                is_active=True
            )
            db.session.add(account)
            db.session.flush() # Получаем ID аккаунта перед сохранением
            print(f"✅ Аккаунт '{account.group_name}' добавлен.")
        else:
            print(f"ℹ️ Используем существующий аккаунт: {account.group_name}")

        # 3. Проверяем наличие бизнес-профиля (нужен для авто-генерации)
        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            print("Adding test Business Profile...")
            profile = BusinessProfile(
                user_id=user_id,
                niche="Кофейня",
                description="Уютная кофейня в центре города с лучшим рафом",
                target_audience="Студенты и фрилансеры"
            )
            db.session.add(profile)
            print("✅ Бизнес-профиль добавлен.")

        # 4. Создаем тестовый пост на «через 3 минуты»
        publish_time = datetime.now() + timedelta(minutes=3)
        
        test_post = Post(
            user_id=user_id,
            vk_account_id=account.id,
            title="Тестовый пост",
            text=f"Проверка демона! Время записи: {datetime.now().strftime('%H:%M:%S')}",
            publish_date=publish_time,
            status='scheduled',
            is_published=False
        )

        db.session.add(test_post)
        db.session.commit()

        print("-" * 30)
        print(f"🚀 ВСЕ ГОТОВО!")
        print(f"Пост ID: {test_post.id}")
        print(f"Время публикации: {publish_time.strftime('%H:%M:%S')}")
        print(f"Теперь запусти 'python run_publisher.py' и жди 3 минуты.")

if __name__ == "__main__":
    setup_test_environment()