import os
from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

# Твои модули
from models import db, User
from database import init_database

app = Flask(__name__)
app.secret_key = 'analytics-dashboard-secret-2025'

# --- ИСПРАВЛЕНИЕ: НАСТРОЙКА БАЗЫ ДАННЫХ ДЛЯ VERCEL ---
# Пытаемся получить ссылку на базу Neon/Postgres
db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

if db_url:
    # Исправляем ссылку для SQLAlchemy (postgres -> postgresql)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    # Добавляем SSL, если нужно (для Neon обычно нужно)
    if '?' not in db_url:
         db_url += "?sslmode=require"
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    # ВАЖНО: Если базы нет (локально или не подключена), используем память!
    # Vercel запрещает писать файлы, поэтому sqlite:///file.db вызовет ошибку.
    print("⚠️ База данных не найдена в переменных. Используем SQLite в оперативной памяти.")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
# -----------------------------------------------------

# Инициализируем логин
login_manager = LoginManager()
login_manager.init_app(app)

# Инициализируем БД (ПОСЛЕ настройки конфига!)
init_database(app)

# Кастомные фильтры
from routes.filters import register_filters
register_filters(app)

@login_manager.user_loader
def load_user(user_id):
    # Импорт внутри функции нужен, чтобы избежать циклических ссылок
    from models import User 
    return User.query.get(int(user_id))

# Импортируем маршруты
from routes.auth import auth_bp
from routes.unified_dashboard import unified_bp
from routes.vk_analytics import vk_bp
from routes.api import api_bp
from routes.addvkaccount import vk_add
from routes.business_setup import setup_bp

# Регистрируем Blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(unified_bp)
app.register_blueprint(vk_bp)
app.register_blueprint(api_bp)
app.register_blueprint(vk_add)
app.register_blueprint(setup_bp)

# Создание таблиц и пользователей при запуске
with app.app_context():
    # Создаем таблицы (если их нет)
    db.create_all()
    
    # Создаем тестового пользователя если нет
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('admin123')
        new_user = User(username='admin', password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        print("✅ Создан тестовый пользователь: admin / admin123")

    if not User.query.filter_by(username='EcoPartner').first():
        hashed_password2 = generate_password_hash('4A9k1*d')
        test_user1 = User(username='EcoPartner', password_hash=hashed_password2)
        db.session.add(test_user1)
        db.session.commit()
        print("✅ Создан тестовый пользователь: EcoPartner / 4A9k1*d")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False)
