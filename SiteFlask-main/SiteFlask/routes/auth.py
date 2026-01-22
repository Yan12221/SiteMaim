from flask import Blueprint, render_template, request, redirect, session
from flask_login import login_user
from models import User
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return redirect('/login')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        # 1. Сначала проверяем, что user не None
        # 2. Затем проверяем пароль
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            session['user_id'] = user.id
            login_user(user)
            return redirect('/unified-dashboard')
        else:
            # Сюда попадем, если пользователя нет ИЛИ пароль не подошел
            error = "Неверный логин или пароль"
            return render_template('login.html', error=error)
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')