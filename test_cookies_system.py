#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы управления cookies
"""

import asyncio
import logging
import json
from database import Database
from utils.cookies_manager import CookiesManager, FingerprintGenerator
from utils.video_downloader_v2 import EnhancedVideoDownloader
import config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_cookies_manager():
    """Тестирует менеджер cookies"""
    logger.info("🧪 Testing Cookies Manager...")
    
    try:
        # Инициализация
        db = Database(config.DATABASE_URL)
        cookies_manager = CookiesManager(db)
        
        # Тестовые cookies для Instagram
        test_cookies = json.dumps([
            {
                "domain": ".instagram.com",
                "name": "test_cookie",
                "value": "test_value",
                "path": "/",
                "secure": True,
                "httpOnly": True
            }
        ])
        
        # Добавляем тестовые cookies
        logger.info("Adding test cookies...")
        success = await cookies_manager.add_cookies(
            platform="instagram",
            cookies_data=test_cookies,
            notes="Test cookies for system check"
        )
        
        if success:
            logger.info("✅ Cookies added successfully!")
        else:
            logger.error("❌ Failed to add cookies")
        
        # Получаем cookies
        logger.info("Getting cookies...")
        cookie_data = await cookies_manager.get_cookies("instagram")
        
        if cookie_data:
            logger.info(f"✅ Got cookies: ID={cookie_data['id']}")
        else:
            logger.warning("⚠️ No cookies found")
        
        # Получаем статистику
        logger.info("Getting statistics...")
        stats = await cookies_manager.get_statistics()
        
        for platform, data in stats.items():
            logger.info(f"📊 {platform}: {data['active']} active, {data['total']} total")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in cookies manager test: {e}")
        return False

async def test_fingerprint_generator():
    """Тестирует генератор fingerprints"""
    logger.info("🧪 Testing Fingerprint Generator...")
    
    platforms = ['instagram', 'tiktok', 'youtube']
    
    for platform in platforms:
        fingerprint = FingerprintGenerator.generate(platform)
        logger.info(f"✅ {platform} fingerprint:")
        logger.info(f"   User-Agent: {fingerprint['user_agent'][:50]}...")
        logger.info(f"   Language: {fingerprint['language']}")
        logger.info(f"   Resolution: {fingerprint['resolution']}")
    
    return True

async def test_video_downloader():
    """Тестирует video downloader"""
    logger.info("🧪 Testing Video Downloader...")
    
    try:
        # Инициализация
        db = Database(config.DATABASE_URL)
        cookies_manager = CookiesManager(db)
        downloader = EnhancedVideoDownloader(
            cookies_manager=cookies_manager,
            db=db
        )
        
        # Тестовые URL для проверки детекции платформ
        test_urls = [
            "https://www.tiktok.com/@test/video/123456",
            "https://www.youtube.com/shorts/abc123",
            "https://www.instagram.com/reel/xyz789"
        ]
        
        for url in test_urls:
            platform = downloader.detect_platform(url)
            if platform:
                logger.info(f"✅ Detected {platform} for {url}")
            else:
                logger.error(f"❌ Failed to detect platform for {url}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in video downloader test: {e}")
        return False

async def test_integration():
    """Тестирует полную интеграцию"""
    logger.info("🧪 Testing Full Integration...")
    
    try:
        # Проверяем наличие DATABASE_URL
        if not config.DATABASE_URL:
            logger.warning("⚠️ DATABASE_URL not configured, skipping integration test")
            return False
        
        # Инициализация всех компонентов
        db = Database(config.DATABASE_URL)
        cookies_manager = CookiesManager(db)
        downloader = EnhancedVideoDownloader(
            cookies_manager=cookies_manager,
            db=db
        )
        
        logger.info("✅ All components initialized successfully!")
        
        # Проверяем статистику
        stats = await cookies_manager.get_statistics()
        
        total_cookies = sum(s.get('total', 0) for s in stats.values())
        active_cookies = sum(s.get('active', 0) for s in stats.values())
        
        logger.info(f"📊 System status:")
        logger.info(f"   Total cookies: {total_cookies}")
        logger.info(f"   Active cookies: {active_cookies}")
        
        if active_cookies == 0:
            logger.warning("⚠️ No active cookies! Add cookies through admin panel")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in integration test: {e}")
        return False

async def main():
    """Главная функция тестирования"""
    logger.info("=" * 50)
    logger.info("🚀 COOKIES SYSTEM TEST")
    logger.info("=" * 50)
    
    tests = [
        ("Fingerprint Generator", test_fingerprint_generator),
        ("Cookies Manager", test_cookies_manager),
        ("Video Downloader", test_video_downloader),
        ("Full Integration", test_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n📝 Running: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}")
            results.append((test_name, False))
        logger.info("-" * 30)
    
    # Итоги
    logger.info("\n" + "=" * 50)
    logger.info("📊 TEST RESULTS:")
    logger.info("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("-" * 50)
    logger.info(f"Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All tests passed! System is ready to use!")
    else:
        logger.warning(f"⚠️ {failed} tests failed. Please check the logs above.")
    
    return failed == 0

if __name__ == "__main__":
    # Запускаем тесты
    success = asyncio.run(main())
    exit(0 if success else 1)
