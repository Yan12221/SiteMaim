from flask import Blueprint, jsonify, render_template, request, redirect, session
from services.ai_service import ai_service
from models import db, BusinessProfile, VKAccount, VKStatistic

setup_bp = Blueprint('setup', __name__)

@setup_bp.route('/business-setup', methods=['GET', 'POST'])
def business_setup():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    profile = BusinessProfile.query.filter_by(user_id=user_id).first()
    
    if request.method == 'POST':
        try:
            # 1. Сначала обрабатываем данные бизнеса (это важнее всего)
            if not profile:
                profile = BusinessProfile(user_id=user_id)
                db.session.add(profile)
            
            profile.niche = request.form.get('niche')
            profile.description = request.form.get('description')
            profile.target_audience = request.form.get('target_audience')
            profile.goals = request.form.get('goals')
            
            raw_stop_words = request.form.get('stop_words', '')
            profile.stop_words = ",".join([w.strip() for w in raw_stop_words.split(',') if w.strip()])

            # 2. Обработка VK (делаем её необязательной, чтобы не блокировать стратегию)
            group_id = request.form.get('group_id')
            access_token = request.form.get('access_token')
            
            if group_id and access_token: 
                vk_acc = VKAccount.query.filter_by(user_id=user_id, group_id=group_id).first()
                if not vk_acc:
                    # Здесь access_token уже точно есть благодаря проверке выше
                    vk_acc = VKAccount(
                        user_id=user_id, 
                        group_id=group_id, 
                        access_token=access_token, # Явно передаем при создании
                        is_active=True
                    )
                    db.session.add(vk_acc)
                    db.session.flush() 
                else:
                    # Если аккаунт уже был, просто обновляем токен
                    vk_acc.access_token = access_token
                
                vk_acc.access_token = access_token
                vk_acc.group_name = request.form.get('group_name') or f"Группа {group_id}"
                
                # Создаем пустую статику если нет
                if not VKStatistic.query.filter_by(vk_account_id=vk_acc.id).first():
                    db.session.add(VKStatistic(vk_account_id=vk_acc.id))

            db.session.commit()

            # 3. Генерация стратегии
            strategy = ai_service.generate_strategy_preview(user_id)
            if not strategy:
                return jsonify({'status': 'error', 'message': 'AI не смог сгенерировать текст'}), 500

            return jsonify({
                'status': 'success',
                'strategy': strategy
            })

        except Exception as e:
            db.session.rollback()
            print(f"❌ ОШИБКА В SETUP: {str(e)}") # См. в консоль!
            return jsonify({'status': 'error', 'message': f'Ошибка сервера: {str(e)}'}), 500

    return render_template('business_setup.html', profile=profile)

@setup_bp.route('/save-confirmed-strategy', methods=['POST'])
def save_confirmed_strategy():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    new_strategy = data.get('strategy')
    
    profile = BusinessProfile.query.filter_by(user_id=session['user_id']).first()
    if profile:
        # Это поле станет основой для фильтрации в AIContentModerator
        profile.BusinessPrompt = new_strategy 
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 404