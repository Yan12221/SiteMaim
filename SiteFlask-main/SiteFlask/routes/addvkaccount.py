from flask import render_template, request, jsonify, redirect, session, Blueprint
from datetime import datetime
from models import VKStatistic, VKAccount, Post, db
import requests

vk_add = Blueprint('vk_add', __name__)

@vk_add.route('/vk-add')
def vk_analytics():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    selected_account_id = request.args.get('group_id', type=int)
    
    # Получаем все VK аккаунты пользователя
    vk_accounts = VKAccount.query.filter_by(user_id=user_id).all()
    
    if not vk_accounts:
        # Если нет групп, показываем пустую страницу с предложением добавить
        return render_template('addvkaccount.html', 
                             vk_accounts=[], 
                             current_stats=None,
                             top_posts=[])
    
    # Если группа не выбрана, берем первую
    if not selected_account_id and vk_accounts:
        selected_account_id = vk_accounts[0].id
    
    # Получаем текущую статистику
    current_stats = VKStatistic.query.filter_by(
        vk_account_id=selected_account_id
    ).order_by(VKStatistic.date.desc()).first()
    
    # Получаем топ постов
    top_posts = Post.query.filter_by(
        vk_account_id=selected_account_id,
        status='published'
    ).order_by(Post.likes.desc()).limit(5).all()
    
    return render_template('DashboardVK.html',
                         vk_accounts=vk_accounts,
                         selected_account_id=selected_account_id,
                         current_stats=current_stats,
                         top_posts=top_posts)

@vk_add.route('/add-vk-account', methods=['GET', 'POST'])
def add_vk_account():
    if 'user_id' not in session:
            return redirect('/login')

    user_id = session['user_id']
    if request.method == 'POST':
        try:
            group_id = request.form.get('group_id')
            group_name = request.form.get('group_name')
            access_token = request.form.get('access_token')
            is_active = request.form.get('is_active') == 'on'
            
            # Проверяем, есть ли уже такая группа у пользователя
            existing_account = VKAccount.query.filter_by(
                user_id=user_id,
                group_id=group_id
            ).first()
            
            if existing_account:
                return jsonify({
                    'success': False,
                    'error': 'Эта группа уже добавлена'
                })
            
            # Если имя группы не указано, получаем его из VK API
            if not group_name:
                group_name = get_group_name_from_vk(group_id, access_token)
            
            # Создаем новую запись
            new_account = VKAccount(
                user_id=session['user_id'],
                group_id=group_id,
                group_name=group_name,
                access_token=access_token,
                is_active=is_active,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_account)
            db.session.commit()
            
            # Сразу получаем начальную статистику
            fetch_vk_statistics(new_account.id)
            
            return jsonify({
                'success': True,
                'message': 'Группа успешно добавлена',
                'account_id': new_account.id
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    return render_template('addvkaccount.html')

def get_group_name_from_vk(group_id, access_token):
    """Получаем название группы из VK API"""
    try:
        # Запрос к VK API для получения информации о группе
        url = f'https://api.vk.com/method/groups.getById'
        params = {
            'group_id': group_id,
            'access_token': access_token,
            'v': '5.131'
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'response' in data and len(data['response']) > 0:
            return data['response'][0]['name']
        else:
            return f'Группа {group_id}'
            
    except Exception:
        return f'Группа {group_id}'

@vk_add.route('/api/vk/fetch/<int:account_id>', methods=['POST'])
def fetch_vk_stats(account_id):
    if 'user_id' not in session:
            return redirect('/login')

    user_id = session['user_id']
    """Обновление статистики из VK API"""
    try:
        # Получаем аккаунт
        account = VKAccount.query.get_or_404(account_id)
        
        # Проверяем права доступа
        if account.user_id != user_id:
            return jsonify({'success': False, 'error': 'Нет доступа'})
        
        # Получаем статистику
        success = fetch_vk_statistics(account_id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не удалось получить статистику'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def fetch_vk_statistics(account_id):
    """Функция получения статистики из VK API"""
    try:
        account = VKAccount.query.get(account_id)
        
        # Получаем статистику группы
        stats = get_vk_group_stats(account.group_id, account.access_token)
        
        # Сохраняем статистику в базу
        vk_stat = VKStatistic(
            vk_account_id=account_id,
            date=datetime.utcnow().date(),
            followers_count=stats.get('members_count', 0),
            reach=stats.get('reach', 0),
            likes=stats.get('likes', 0),
            comments=stats.get('comments', 0),
            shares=stats.get('reposts', 0),
            views=stats.get('views', 0),
            engagement=stats.get('likes', 0) + stats.get('comments', 0) + stats.get('reposts', 0)
        )
        
        db.session.add(vk_stat)
        db.session.commit()
        
        return True
        
    except Exception as e:
        print(f"Error fetching VK stats: {e}")
        return False

def get_vk_group_stats(group_id, access_token):
    """Получение статистики группы из VK API"""
    try:
        # Получаем базовую статистику
        url = 'https://api.vk.com/method/stats.get'
        params = {
            'group_id': group_id,
            'timestamp_from': int((datetime.now().timestamp() - 86400)),  # последние 24 часа
            'timestamp_to': int(datetime.now().timestamp()),
            'access_token': access_token,
            'v': '5.131'
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'response' in data:
            return data['response']
        else:
            return {}
            
    except Exception as e:
        print(f"VK API error: {e}")
        return {}