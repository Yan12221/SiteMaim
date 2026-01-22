from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from models import db, User

app = Flask(__name__)
app.secret_key = 'secret-key-just-for-start'

# --- ЗАГЛУШКА: БАЗА В ОПЕРАТИВНОЙ ПАМЯТИ ---
# Это гарантированно работает на Vercel. 
# Ошибок с файлами быть не может.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# -------------------------------------------

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Импорт маршрутов (если внутри файлов маршрутов нет ошибок импорта, они заработают)
# Если будут ошибки - закомментируй проблемные строки
try:
    from routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    from routes.unified_dashboard import unified_bp
    app.register_blueprint(unified_bp)
    
    # Остальные пока можно отключить, если они вызывают ошибки
    # from routes.vk_analytics import vk_bp
    # app.register_blueprint(vk_bp)
except Exception as e:
    print(f"Ошибка при импорте маршрутов: {e}")

# Создаем таблицы в памяти при запуске
with app.app_context():
    db.create_all()
    # Создаем админа в памяти, чтобы можно было войти
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password_hash=generate_password_hash('admin'))
        db.session.add(admin)
        db.session.commit()
        print("Test admin created")

if __name__ == '__main__':
    app.run(debug=True)
