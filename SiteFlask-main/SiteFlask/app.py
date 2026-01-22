from flask import Flask
from models import db, User
from database import init_database
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from models import User
import os

app = Flask(__name__)
app.secret_key = 'analytics-dashboard-secret-2025'
login_manager = LoginManager()
login_manager.init_app(app)
# Инициализация БД
init_database(app)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "analytics.db")}'

# Кастомные фильры
from routes.filters import register_filters
register_filters(app)

@login_manager.user_loader
def load_user(user_id):
    from models import User  # Импортируем внутри функции
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

with app.app_context():
    # Создаем тестового пользователя если нет
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('admin123')
        new_user = User(username='admin', password_hash=hashed_password)
        print(new_user)
        db.session.add(new_user)
        db.session.commit()
        print("✅ Создан тестовый пользователь: admin / admin123")

        hashed_password2 = generate_password_hash('4A9k1*d')
        test_user1 = User(username='EcoPartner', password_hash=hashed_password2)  # Используем password_hash
        print(test_user1)
        db.session.add(test_user1)
        db.session.commit()
        print("✅ Создан тестовый пользователь: EcoPartner / 4A9k1*d")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False)
