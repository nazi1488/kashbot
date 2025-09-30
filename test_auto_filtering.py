#!/usr/bin/env python3
"""
Тестирование автоматической фильтрации куков при добавлении
"""

import os
import sys
import asyncio
import json
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.cookies_manager import CookiesManager
from database import Database
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_cookies_with_foreign_domains():
    """Создает тестовые куки с посторонними доменами"""
    
    # Смешанные куки для Instagram (валидные + посторонние)
    instagram_cookies = [
        # ✅ Валидные Instagram куки
        {
            "domain": ".instagram.com",
            "name": "sessionid",
            "value": "test_session_id_123",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "expirationDate": 1767225600
        },
        {
            "domain": ".facebook.com", 
            "name": "c_user",
            "value": "100012345678",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        },
        # ❌ Посторонние куки (должны быть удалены)
        {
            "domain": "telegram.me",
            "name": "stel_web_auth", 
            "value": "https%3A%2F%2Fweb.telegram.org%2Fk%2F",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1789425565
        },
        {
            "domain": ".google.com",
            "name": "NID",
            "value": "511=abcdef123456",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "expirationDate": 1767225600
        },
        {
            "domain": ".youtube.com",
            "name": "VISITOR_INFO1_LIVE",
            "value": "xyz789",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        }
    ]
    
    # Смешанные куки для YouTube (валидные + посторонние)
    youtube_cookies = [
        # ✅ Валидные YouTube куки
        {
            "domain": ".youtube.com",
            "name": "VISITOR_INFO1_LIVE", 
            "value": "valid_youtube_visitor",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        },
        {
            "domain": ".google.com",
            "name": "SID",
            "value": "google_session_123",
            "path": "/", 
            "secure": True,
            "httpOnly": True,
            "expirationDate": 1767225600
        },
        # ❌ Посторонние куки (должны быть удалены)
        {
            "domain": ".instagram.com",
            "name": "sessionid",
            "value": "instagram_session_456",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "expirationDate": 1767225600
        },
        {
            "domain": ".tiktok.com",
            "name": "tt_webid",
            "value": "tiktok_webid_789",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        }
    ]
    
    # Смешанные куки для TikTok (валидные + посторонние)
    tiktok_cookies = [
        # ✅ Валидные TikTok куки
        {
            "domain": ".tiktok.com",
            "name": "tt_webid",
            "value": "valid_tiktok_webid",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        },
        {
            "domain": ".bytedance.com",
            "name": "bd_ticket_guard",
            "value": "bytedance_guard_123",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "expirationDate": 1767225600
        },
        # ❌ Посторонние куки (должны быть удалены)
        {
            "domain": ".facebook.com",
            "name": "c_user",
            "value": "facebook_user_123",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        },
        {
            "domain": ".google.com",
            "name": "APISID", 
            "value": "google_api_456",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expirationDate": 1767225600
        }
    ]
    
    return {
        'instagram': json.dumps(instagram_cookies),
        'youtube': json.dumps(youtube_cookies), 
        'tiktok': json.dumps(tiktok_cookies)
    }


async def test_auto_filtering():
    """Тестирует автоматическую фильтрацию куков"""
    
    try:
        db = Database(DATABASE_URL)
        manager = CookiesManager(db)
        
        print("🧪 ТЕСТИРОВАНИЕ АВТОМАТИЧЕСКОЙ ФИЛЬТРАЦИИ КУКОВ")
        print("=" * 60)
        
        # Получаем тестовые куки с посторонними доменами
        test_cookies = create_test_cookies_with_foreign_domains()
        
        for platform, cookies_json in test_cookies.items():
            print(f"\n🔍 Тестируем фильтрацию для {platform.upper()}")
            print("-" * 40)
            
            # Показываем исходное количество куков
            original_cookies = json.loads(cookies_json)
            print(f"📥 Исходно куков: {len(original_cookies)}")
            
            # Показываем домены в исходных куках
            domains = {cookie.get('domain', '') for cookie in original_cookies}
            print(f"🌐 Исходные домены: {', '.join(domains)}")
            
            # Добавляем куки (с автоматической фильтрацией)
            success = await manager.add_cookies(
                platform=platform,
                cookies_data=cookies_json,
                notes=f"Test cookies for {platform}",
                added_by=1  # Test admin ID
            )
            
            if success:
                print(f"✅ Куки для {platform} успешно добавлены с автофильтрацией")
                
                # Проверяем что сохранилось в базе
                cookies_from_db = await manager.get_cookies(platform)
                if cookies_from_db:
                    saved_cookies = cookies_from_db['cookies']
                    saved_domains = {cookie.get('domain', '') for cookie in saved_cookies}
                    
                    print(f"💾 Сохранено куков: {len(saved_cookies)}")
                    print(f"🌐 Сохраненные домены: {', '.join(saved_domains)}")
                    
                    # Проверяем, что посторонние домены удалены
                    allowed_domains = manager.allowed_domains.get(platform, set())
                    
                    foreign_domains_found = []
                    for domain in saved_domains:
                        is_allowed = any(domain == ad or domain.endswith(ad) for ad in allowed_domains)
                        if not is_allowed:
                            foreign_domains_found.append(domain)
                    
                    if foreign_domains_found:
                        print(f"❌ ОШИБКА: Найдены посторонние домены: {foreign_domains_found}")
                    else:
                        print(f"✅ Все домены валидны для {platform}")
                        
                else:
                    print(f"❌ Не удалось получить сохраненные куки для {platform}")
            else:
                print(f"❌ Не удалось добавить куки для {platform}")
        
        print(f"\n🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
        print(f"\n📋 Проверьте логи выше на наличие сообщений о фильтрации")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🧪 Тестирование автоматической фильтрации куков...")
    asyncio.run(test_auto_filtering())
