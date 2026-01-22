// Подключение API (VK/Telegram)
document.getElementById('apiSetupForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const apiType = document.querySelector('input[name="apiType"]:checked').value;
    
    const formData = {
        api_type: apiType,
        token: document.getElementById('apiToken').value,
        target_id: document.getElementById('targetId').value
    };
    
    try {
        const response = await fetch('/setup-api', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        showAlert(data.message, data.status === 'success' ? 'success' : 'danger');
    } catch (error) {
        showAlert('Ошибка подключения', 'danger');
    }
});

// Переключение между VK и Telegram
document.querySelectorAll('input[name="apiType"]').forEach(radio => {
    radio.addEventListener('change', function() {
        updateApiFields(this.value);
    });
});

function updateApiFields(apiType) {
    const tokenInput = document.getElementById('apiToken');
    const targetInput = document.getElementById('targetId');
    const tokenLabel = document.getElementById('tokenLabel');
    const idLabel = document.getElementById('idLabel');
    const tokenHelp = document.getElementById('tokenHelp');
    const idHelp = document.getElementById('idHelp');
    
    if (apiType === 'vk') {
        // Настройки для VK
        tokenLabel.textContent = 'Access Token VK';
        tokenInput.placeholder = 'VK Access Token...';
        tokenHelp.innerHTML = 'Токен для доступа к API VK. Можно получить в <a href="https://vk.com/dev/access_token" target="_blank">настройках приложения VK</a>';
        
        idLabel.textContent = 'ID группы';
        targetInput.placeholder = '123456789';
        idHelp.textContent = 'Числовой ID группы VK (без знака минус)';
        
    } else if (apiType === 'telegram') {
        // Настройки для Telegram
        tokenLabel.textContent = 'Bot Token Telegram';
        tokenInput.placeholder = 'Bot Token...';
        tokenHelp.innerHTML = 'Токен бота Telegram. Можно получить у <a href="https://t.me/BotFather" target="_blank">@BotFather</a>';
        
        idLabel.textContent = 'ID канала/чата';
        targetInput.placeholder = '@channelname или -1001234567890';
        idHelp.textContent = 'Имя канала (с @) или числовой ID (для приватных каналов)';
    }
    
    // Очищаем поля при переключении
    tokenInput.value = '';
    targetInput.value = '';
}

// Инициализация полей при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const defaultApiType = document.querySelector('input[name="apiType"]:checked').value;
    updateApiFields(defaultApiType);
});