import requests
from typing import Dict
from abc import ABC, abstractmethod
from utils.logger import get_logger

logger = get_logger(__name__)

class SocialMediaAPI(ABC):
    """Базовый класс для API социальных сетей"""
    
    @abstractmethod
    def publish(self, content: Dict, business_info: Dict) -> Dict:
        """Публикация контента"""
        pass

class SocialMediaPublisher:
    """Универсальный публикатор для всех соцсетей"""
    
    def __init__(self):
        # Здесь мы регистрируем все доступные API
        self.apis = {
            'vk': VKontakteAPI(),
            # Если добавишь TelegramAPI, его нужно будет вписать сюда
        }
    
    def publish(self, platform: str, content: Dict, business_info: Dict) -> Dict:
        """Метод для публикации на выбранной платформе"""
        api = self.apis.get(platform)
        
        if not api:
            logger.error(f"API для платформы {platform} не найден")
            return {'success': False, 'error': f'Platform {platform} not supported'}
        
        # Вызываем метод publish у конкретного API (например, у VKontakteAPI)
        return api.publish(content, business_info)
    
class VKontakteAPI(SocialMediaAPI):
    """API ВКонтакте (С поддержкой загрузки фото)"""
    
    def __init__(self):
        self.api_version = "5.199"
    
    def _upload_photo(self, image_url, access_token, group_id):
        """Вспомогательный метод: Скачивает фото по ссылке и грузит в VK"""
        try:
            # 1. Получаем адрес сервера для загрузки
            server_url = "https://api.vk.com/method/photos.getWallUploadServer"
            server_resp = requests.get(server_url, params={
                'access_token': access_token,
                'group_id': group_id,
                'v': self.api_version
            }).json()

            if 'error' in server_resp:
                logger.error(f"VK Upload Server Error: {server_resp['error']}")
                return None

            upload_url = server_resp['response']['upload_url']

            # 2. Скачиваем картинку (байты)
            img_data = requests.get(image_url).content

            # 3. Отправляем файл на сервер VK
            files = {'photo': ('image.jpg', img_data, 'image/jpeg')}
            upload_resp = requests.post(upload_url, files=files).json()

            # 4. Сохраняем фото в альбом группы
            save_url = "https://api.vk.com/method/photos.saveWallPhoto"
            save_resp = requests.post(save_url, params={
                'access_token': access_token,
                'group_id': group_id,
                'photo': upload_resp['photo'],
                'server': upload_resp['server'],
                'hash': upload_resp['hash'],
                'v': self.api_version
            }).json()
            
            if 'error' in save_resp:
                logger.error(f"VK Save Photo Error: {save_resp['error']}")
                return None

            # 5. Возвращаем ID вложения (photo-GROUP_ID_PHOTO_ID)
            photo_obj = save_resp['response'][0]
            return f"photo{photo_obj['owner_id']}_{photo_obj['id']}"

        except Exception as e:
            logger.error(f"Critical upload error: {e}")
            return None

    def publish(self, content: Dict, business_info: Dict) -> Dict:
        """Публикация в VK"""
        try:
            group_id = business_info.get('vk_group_id')
            access_token = business_info.get('access_token')
            
            if not access_token:
                return {'success': False, 'error': 'No access token provided'}

            params = {
                'access_token': access_token,
                'v': self.api_version,
                'owner_id': f"-{group_id}",
                'from_group': 1,
                'message': f"{content.get('title', '')}\n\n{content.get('text', '')}"
            }

            # Если есть дата публикации (отложенный пост в самом VK)
            if content.get('publish_date'):
                params['publish_date'] = content.get('publish_date')

            # --- ОБРАБОТКА ИЗОБРАЖЕНИЯ ---
            if content.get('image_url'):
                logger.info("📸 Загружаю фото в VK...")
                photo_attachment = self._upload_photo(
                    content['image_url'], 
                    access_token, 
                    group_id
                )
                if photo_attachment:
                    params['attachments'] = photo_attachment
            # -----------------------------
            
            response = requests.post("https://api.vk.com/method/wall.post", params=params)
            result = response.json()
            
            if 'error' in result:
                logger.error(f"VK API Error: {result['error']}")
                return {'success': False, 'error': result['error']}
            
            post_id = result['response']['post_id']
            logger.info(f"✅ Пост опубликован в VK, ID: {post_id}")
            return {'success': True, 'post_id': post_id}
            
        except Exception as e:
            logger.error(f"Ошибка публикации в VK: {e}")
            return {'success': False, 'error': str(e)}