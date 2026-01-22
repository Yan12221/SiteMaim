from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

# Создаем пустой объект, подключим его позже в app.py
db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)

    # Заглушки методов, чтобы Flask-Login не ругался
    def get_id(self):
        return str(self.id)
