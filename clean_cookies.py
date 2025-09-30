#!/usr/bin/env python3
"""
Очистка куков от посторонних доменов (Telegram, Google и т.д.)
"""

import os
import sys
import asyncio
import json
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Database
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_cookies_json(cookies_json: str, platform: str) -> str:
    """Очищает JSON куки от посторонних доменов"""
    
    # Разрешенные домены для каждой платформы
    ALLOWED_DOMAINS = {
        'instagram': {
            '.instagram.com',
            'instagram.com',
            '.facebook.com',
            'facebook.com',
            '.fbcdn.net',
            'fbcdn.net'
        },
        'youtube': {
            '.youtube.com',
            'youtube.com', 
            '.google.com',
            'google.com',
            '.googleapis.com',
            'googleapis.com',
            '.googlevideo.com',
            'googlevideo.com'
        },
        'tiktok': {
            '.tiktok.com',
            'tiktok.com',
            '.musical.ly',
            'musical.ly',
            '.bytedance.com',
            'bytedance.com'
        }
    }
    
    try:
        cookies = json.loads(cookies_json)
        allowed_domains = ALLOWED_DOMAINS.get(platform, set())
        
        # Фильтруем куки
        clean_cookies = []
        removed_count = 0
        
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
                
            domain = cookie.get('domain', '').lower()
            
            # Проверяем, разрешен ли домен
            is_allowed = False
            
            for allowed_domain in allowed_domains:
                if domain == allowed_domain or domain.endswith(allowed_domain):
                    is_allowed = True
                    break
            
            if is_allowed:
                clean_cookies.append(cookie)
            else:
                removed_count += 1
                logger.info(f"   🗑️  Удален cookie: {cookie.get('name', 'unknown')}@{domain}")
        
        logger.info(f"   📊 Удалено {removed_count} посторонних куков, осталось {len(clean_cookies)}")
        
        return json.dumps(clean_cookies)
        
    except Exception as e:
        logger.error(f"Ошибка очистки куков: {e}")
        return cookies_json


async def clean_all_cookies():
    """Очищает все куки в базе данных"""
    
    try:
        db = Database(DATABASE_URL)
        
        print("🧹 ОЧИСТКА КУКОВ ОТ ПОСТОРОННИХ ДОМЕНОВ")
        print("=" * 50)
        
        # Получаем все куки
        query = """
            SELECT id, platform, cookies_json, notes
            FROM platform_cookies
            WHERE is_active = TRUE AND deleted_at IS NULL
            ORDER BY platform, id
        """
        
        cookies_records = await db.execute(query, fetch=True)
        
        if not cookies_records:
            print("❌ Куки не найдены в базе данных")
            return
        
        print(f"📋 Найдено {len(cookies_records)} записей с куками")
        
        cleaned_count = 0
        
        for record in cookies_records:
            cookie_id = record['id']
            platform = record['platform']
            original_json = record['cookies_json']
            notes = record.get('notes', '')
            
            print(f"\n🔍 Обрабатываем куки ID:{cookie_id} ({platform})")
            
            # Проверяем, есть ли посторонние домены
            try:
                original_cookies = json.loads(original_json)
                
                # Находим посторонние домены
                foreign_domains = set()
                
                for cookie in original_cookies:
                    if isinstance(cookie, dict):
                        domain = cookie.get('domain', '').lower()
                        
                        # Проверяем специфичные паттерны
                        if any(x in domain for x in ['telegram', 'google', 'youtube', 'facebook']) and platform != 'youtube':
                            if platform == 'instagram' and any(x in domain for x in ['facebook', 'fbcdn']):
                                continue  # Facebook куки разрешены для Instagram
                            foreign_domains.add(domain)
                
                if foreign_domains:
                    print(f"   🚨 Найдены посторонние домены: {', '.join(foreign_domains)}")
                    
                    # Очищаем куки
                    clean_json = clean_cookies_json(original_json, platform)
                    
                    # Обновляем в базе данных
                    update_query = """
                        UPDATE platform_cookies 
                        SET cookies_json = %s,
                            notes = %s
                        WHERE id = %s
                    """
                    
                    updated_notes = f"{notes} [CLEANED]" if notes else "[CLEANED]"
                    
                    await db.execute(update_query, (clean_json, updated_notes, cookie_id))
                    
                    print(f"   ✅ Куки очищены и обновлены в базе")
                    cleaned_count += 1
                else:
                    print(f"   ✅ Куки чистые, обновление не требуется")
                    
            except Exception as e:
                print(f"   ❌ Ошибка обработки: {e}")
        
        print(f"\n🎉 ОЧИСТКА ЗАВЕРШЕНА!")
        print(f"   📊 Обработано записей: {len(cookies_records)}")
        print(f"   🧹 Очищено записей: {cleaned_count}")
        
        if cleaned_count > 0:
            print(f"\n🔄 Рекомендуется перезапустить бота для применения изменений")
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки: {e}")


if __name__ == "__main__":
    print("🧹 Очистка куков от посторонних доменов...")
    asyncio.run(clean_all_cookies())
