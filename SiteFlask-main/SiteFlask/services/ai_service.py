from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from urllib.parse import quote
import requests
import os
from datetime import datetime, timedelta

load_dotenv(dotenv_path='os.env')
api_key = os.getenv("INFERENCE_API_KEY")

class AIService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="google/gemma-3-27b-instruct/bf-16",
            base_url="https://api.inference.net/v1",
            api_key=api_key
        )
    
    def generate_strategy_preview(self, user_id):
        from models import BusinessProfile
        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        if not profile: return None

        context = f"Ниша: {profile.niche}, Описание: {profile.description}, ЦА: {profile.target_audience}, Цели: {profile.goals}, Стоп-слова: {profile.stop_words}"
        prompt = f"На основе данных: {context}. Подготовь краткую SMM-стратегию (до 500 симв). Не используй markdown-разметку."
        
        response = self.llm.invoke(prompt)
        return response.content # Возвращаем текст, не сохраняя в БД

    def generate_theme_ideas(self, user_id, strategy):
        """Генерация идей и сохранение в БД"""
        from models import db, PostTheme  

        listThemes = []
        themes = PostTheme.query.filter_by(user_id=user_id).all()
        
        for t in themes:
            listThemes.append(t.theme_text)
        
        prompt = f"""Ты нейросеть, которая помогает создавать идеи для постов в соцсетях.
        Вот стратегия развития бизнеса: {strategy}.
        Предложи 5 интересных тем для постов. 
        Ответь ТОЛЬКО списком тем, каждая с новой строки, без цифр и лишнего текста. Темы, которые уже есть в базе не предлагай: {listThemes}."""
        
        try:
            response = self.llm.invoke(prompt)
            # Получаем текст ответа (зависит от версии langchain, обычно response.content)
            ideas_text = response.content.strip() 
            
            # Очищаем список от лишних символов
            ideas_list = [
                idea.strip("- •12345. ").strip() 
                for idea in ideas_text.split("\n") 
                if idea.strip()
            ][:5] # Берем ровно 5

            for theme_text in ideas_list:
                new_theme = PostTheme(user_id=user_id, theme_text=theme_text)
                db.session.add(new_theme)
            
            db.session.commit()
            print(f"✅ Успешно сохранено {len(ideas_list)} тем в БД для пользователя {user_id}")
            return ideas_list
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка генерации/сохранения тем: {str(e)}")
            return []
        
    def generate_post_content(self, idea):
        print(f"💡 Идея для поста: {idea}")
        
        """Генерация текста поста на основе промпта пользователя"""
        prompt_text = f"""Ты нейросеть, которая публикует посты в VK
        Создай пост на тему: "{idea}"
        Сделай его интересным и информативным, чтобы привлечь внимание аудитории.
        В конце напиши теги по теме поста через запятую.
        Максимальная длина поста - 500 символов. Не применяй Markdown-разметку"""
        
        try:
            response_text = self.llm.invoke(prompt_text)
            description = response_text.text.strip()
            return description
        except Exception as e:
            print(f"Ошибка генерации текста: {str(e)}")
            return None
            
    def generate_planned_date(self, idea, strategy):
        today = datetime.utcnow().strftime('%Y-%m-%d')
        prompt = f"""Ты SMM-планировщик. 
        Сегодняшняя дата: {today}. 
        На основе стратегии: {strategy} 
        Выбери идеальную дату и время для публикации поста на тему "{idea}" в ближайшие 30 дней.
        Ответь ТОЛЬКО в формате: ГГГГ-ММ-ДД ЧЧ:ММ"""
        
        try:
            response = self.llm.invoke(prompt)
            date_str = response.content.strip()
            # Парсим строку в объект datetime
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M')
        except Exception as e:
            print(f"Ошибка планирования даты: {e}")
            # Резервный вариант: сегодня через 2 часа
            return datetime.utcnow() + timedelta(hours=2)
    
    def check_on_idea(self, user_id, description, idea):
        from models import PostTheme, BusinessProfile
        """Проверка идеи на дубли с архивом тем"""

        # Берем ВСЕ темы из базы
        all_themes = PostTheme.query.filter_by(user_id=user_id).order_by(PostTheme.id.desc()).all()
        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        
        archive_themes = [t.theme_text for t in all_themes][5:] # Пропускаем первые 5 новых
        print(profile.stop_words)
        if not archive_themes:
            return "НОВАЯ ТЕМА"

        # Улучшенный промпт с четкой логикой
        prompt = f"""Инструкция: Сравни новую тему с архивом прошлых постов. 
        Если новая тема по смыслу ДУБЛИРУЕТ одну из старых, ответь "ДУБЛЬ: [текст старой темы]".
        Если тема уникальна и не повторяет архив, ответь "УНИКАЛЬНО".
        Если в тексте поста есть стоп-слова или они похожи по смыслу, также пиши "ДУБЛЬ": [Текст поста и капслоком то, где ты нашел стоп-слова]. 
        Новая тема: {idea}
        Текст поста: {description}
        Стоп-слова: {profile.stop_words}
        Архив тем:
        {chr(10).join(archive_themes)}
        """

        try:
            response = self.llm.invoke(prompt)
            res_text = response.content.strip()
            
            if "ДУБЛЬ" in res_text.upper():
                return res_text # Вернет "ДУБЛЬ: Название темы"
            return "НОВАЯ ТЕМА"
        
        except Exception as e:
            print(f"Ошибка проверки: {e}")
            return "НОВАЯ ТЕМА"
        
    def generate_image_prompt(self, idea):
        """Генерация промпта для изображения"""
        prompt_image = f"""Ты нейросеть, которая создает изображения по текстовому описанию. 
        Создай промпт для создания картинки по следующему описанию: {idea}
        Сделай картинку яркой и привлекательной.
        Ничего не говори, только говори промпт. Причем промпт должен состоять из одного слова."""
        
        try:
            response_image = self.llm.invoke(prompt_image)
            image_prompt = response_image.text.strip()
            return image_prompt
        except Exception as e:
            print(f"Ошибка генерации промпта для изображения: {str(e)}")
            return None
        
    def generate_image_url(self, image_prompt):
        """Генерация URL изображения через Pollinations AI"""
        if not image_prompt:
            return None
            
        try:
            encoded_prompt = quote(image_prompt)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
            return image_url
        except Exception as e:
            print(f"Ошибка генерации URL изображения: {str(e)}")
            return None
    
    def download_image(self, image_url, filename="generated_image.jpg"):
        """Скачивание изображения по URL"""
        try:
            response = requests.get(image_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return filename
        except Exception as e:
            print(f"Ошибка скачивания изображения: {str(e)}")
            return None
    
    def process_single_idea(self, idea):
        """Метод для генерации полного пакета данных для ОДНОЙ идеи"""
        try:
            description = self.generate_post_content(idea)
            if not description: return None, None
            
            image_prompt = self.generate_image_prompt(idea)
            image_url = self.generate_image_url(image_prompt) if image_prompt else None
            
            return description, image_url
        except Exception as e:
            print(f"Ошибка: {e}")
            return None, None
        
    def download_image_bytes(self, image_url):
        """Скачивание изображения и возврат bytes"""
        try:
            response = requests.get(image_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Читаем изображение как bytes
            image_bytes = response.content
            
            # Проверяем, что это валидное изображение
            return image_bytes
        except Exception as e:
            print(f"❌ Ошибка скачивания изображения: {str(e)}")
            return None
        
# Создаем глобальный экземпляр сервиса
ai_service = AIService()