from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import os
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_database(app):
    # 1. Определяем корень проекта (где лежит этот файл с БД)
    # Если этот код в папке корня, то:
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # 2. Формируем путь к папке instance или корню
    db_path = os.path.join(basedir, "instance", "analytics.db")
    
    # Убеждаемся, что папка instance существует, иначе SQLite не сможет создать файл
    if not os.path.exists(os.path.join(basedir, "instance")):
        os.makedirs(os.path.join(basedir, "instance"))

    # 3. Принудительно ставим АБСОЛЮТНЫЙ путь (4 слеша для Windows)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        os.environ.get("DATABASE_URL") or 
        f"sqlite:///{db_path}"
    )
    
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print(f"✅ База инициализирована по пути: {db_path}")