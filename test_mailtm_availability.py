#!/usr/bin/env python3
"""
Простой тест доступности Mail.tm API
"""

import asyncio
import aiohttp
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mailtm_api():
    """Тест доступности Mail.tm API"""
    base_url = "https://api.mail.tm"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Тест базовой доступности
            logger.info("Testing Mail.tm API availability...")
            
            # Тест получения доменов
            async with session.get(f"{base_url}/domains") as response:
                logger.info(f"GET /domains - Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Response data: {data}")
                    
                    domains = data.get("hydra:member", [])
                    if domains:
                        logger.info(f"✅ Found {len(domains)} domains:")
                        for domain in domains[:3]:  # Показываем первые 3
                            logger.info(f"  - {domain.get('domain', 'Unknown')}")
                    else:
                        logger.warning("⚠️ No domains found in response")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ API request failed: {response.status}")
                    logger.error(f"Error response: {error_text}")
                    
    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")

async def test_alternative_endpoints():
    """Тест альтернативных endpoints"""
    endpoints = [
        "https://api.mail.tm/domains",
        "https://api.mail.tm/",
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in endpoints:
            try:
                logger.info(f"Testing {url}...")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    logger.info(f"  Status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.info(f"  Content-Type: {content_type}")
                        
                        if 'json' in content_type:
                            data = await response.json()
                            logger.info(f"  JSON response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        else:
                            text = await response.text()
                            logger.info(f"  Text response (first 100 chars): {text[:100]}")
                    else:
                        error_text = await response.text()
                        logger.warning(f"  Error: {error_text[:100]}")
                        
            except Exception as e:
                logger.error(f"  Error testing {url}: {e}")

if __name__ == "__main__":
    logger.info("🧪 Testing Mail.tm API availability...")
    
    asyncio.run(test_mailtm_api())
    
    logger.info("\n🔍 Testing alternative endpoints...")
    asyncio.run(test_alternative_endpoints())
    
    logger.info("\n✅ Test completed!")
