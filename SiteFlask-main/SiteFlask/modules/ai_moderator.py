from typing import Dict, List
from dataclasses import dataclass
from openai import OpenAI  # <--- Новый импорт
import numpy as np
from datetime import datetime
import json

from config.settings import ai_config
from utils.logger import get_logger

logger = get_logger(__name__)

# Инициализация клиента OpenAI (v1.0+)
client = OpenAI(api_key=ai_config.OPENAI_API_KEY)

logger = get_logger(__name__)

@dataclass
class ModerationResult:
    passed: bool
    score: float
    issues: List[str]
    suggestions: List[str]
    check_details: Dict[str, any]

class AIContentModerator:
    def __init__(self, business_info: Dict):
        self.business_info = business_info
        self.stop_words = set(business_info.get('stop_words', []))
        self.brand_values = business_info.get('brand_values', [])
        self.target_topics = business_info.get('topics', [])
        self.published_content = []

    def moderate_content(self, content: Dict) -> ModerationResult:
        logger.info(f"🔎 Модерация: {content.get('title')}")
        
        issues = []
        suggestions = []
        scores = {}
        
        # 1. Стоп-слова (Локальная проверка)
        stop_check = self._check_stop_words(content['text'])
        scores['stop_words'] = stop_check['score']
        if not stop_check['passed']:
            issues.extend(stop_check['issues'])

        # 2. Релевантность теме (AI)
        topic_check = self._check_topic_relevance(content)
        scores['topic'] = topic_check['score']
        if not topic_check['passed']:
            issues.extend(topic_check['issues'])

        # 3. AI Quality Check (AI)
        quality_check = self._ai_quality_check(content)
        scores['quality'] = quality_check['score']
        if not quality_check['passed']:
             issues.extend(quality_check['issues'])

        # Расчет итогов
        overall_score = np.mean(list(scores.values()))
        passed = len(issues) == 0 and overall_score >= 0.7

        return ModerationResult(passed, overall_score, issues, suggestions, scores)

    def _check_stop_words(self, text: str) -> Dict:
        text_lower = text.lower()
        found = [w for w in self.stop_words if w.lower() in text_lower]
        return {
            'passed': len(found) == 0,
            'score': 1.0 if not found else 0.0,
            'issues': [f"Стоп-слово: {w}" for w in found]
        }

    def _call_openai(self, prompt: str) -> Dict:
        """Универсальный метод для вызова нового API"""
        try:
            response = client.chat.completions.create(
                model=ai_config.MODEL_NAME, # gpt-4o-mini или gpt-3.5-turbo
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" } # Гарантирует JSON  
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return {}

    def _check_topic_relevance(self, content: Dict) -> Dict:
        prompt = f"""
        Ты строгий модератор контента.
        Бизнес: {', '.join(self.target_topics)}.
        Текст: {content.get('text')}
        Оцени релевантность теме от 0.0 до 1.0. Верни JSON: {{ "score": float, "reason": str }}
        """
        res = self._call_openai(prompt)
        score = res.get('score', 0.5)
        print(score)
        return {
            'passed': score >= 0.7, 
            'score': score, 
            'issues': [res.get('reason')] if score < 0.7 else []
        }

    def _ai_quality_check(self, content: Dict) -> Dict:
        prompt = f"""
        Проверь качество текста для соцсетей.
        Текст: {content.get('text')}
        Оцени (0.0-1.0) по критериям: грамматика, стиль, продающая структура.
        Верни JSON: {{ "score": float, "issues": [str] }}
        """
        res = self._call_openai(prompt)
        score = res.get('score', 0.7) # Дефолт, если AI упал, но тут он не упадет
        return {
            'passed': score >= 0.6,
            'score': score,
            'issues': res.get('issues', [])
        }
    
    def add_to_published(self, content: Dict):
        """Добавить контент в историю опубликованного"""
        content['published_at'] = datetime.now()
        self.published_content.append(content)
        logger.info(f"Контент добавлен в историю: {content.get('title', 'Без заголовка')}")
    
    def get_moderation_report(self, result: ModerationResult) -> str:
        """Генерация отчета о модерации"""
        report = f"""
        📊 ОТЧЕТ О МОДЕРАЦИИ КОНТЕНТА
        {'='*50}
        
        Статус: {'✅ ОДОБРЕНО' if result.passed else '❌ ОТКЛОНЕНО'}
        Общий балл: {result.score:.2%}
        
        Детальные оценки:
        {'-'*50}
        """
        
        for check_name, score in result.check_details.items():
            emoji = '✅' if score >= 0.7 else '⚠️' if score >= 0.5 else '❌'
            report += f"\n{emoji} {check_name}: {score:.2%}"
        
        if result.issues:
            report += f"\n\n❌ Обнаруженные проблемы:\n"
            for i, issue in enumerate(result.issues, 1):
                report += f"{i}. {issue}\n"
        
        if result.suggestions:
            report += f"\n💡 Рекомендации:\n"
            for i, suggestion in enumerate(result.suggestions, 1):
                report += f"{i}. {suggestion}\n"
        
        return report