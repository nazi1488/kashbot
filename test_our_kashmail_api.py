#!/usr/bin/env python3
"""
Тест нашего KashMail API клиента
"""

import asyncio
import logging
from services.kashmail_api import MailTmApi

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_our_api():
    """Тест нашего API клиента"""
    logger.info("🧪 Testing our KashMail API client...")
    
    api = MailTmApi(timeout_seconds=10)
    
    try:
        # Тест получения доменов
        logger.info("Testing get_domains()...")
        domains = await api.get_domains()
        
        if domains:
            logger.info(f"✅ Successfully got domains: {domains}")
            
            # Пробуем создать аккаунт
            logger.info("Testing create_account()...")
            result = await api.create_account(domains[0])
            
            if result:
                email, password, account_id = result
                logger.info(f"✅ Successfully created account: {email}")
                
                # Пробуем получить JWT
                logger.info("Testing get_jwt_token()...")
                jwt = await api.get_jwt_token(email, password)
                
                if jwt:
                    logger.info(f"✅ Successfully got JWT token")
                    
                    # Пробуем получить сообщения
                    logger.info("Testing get_messages()...")
                    messages = await api.get_messages(jwt)
                    
                    if messages is not None:
                        logger.info(f"✅ Successfully got messages: {len(messages)} messages")
                    else:
                        logger.error("❌ Failed to get messages")
                else:
                    logger.error("❌ Failed to get JWT token")
            else:
                logger.error("❌ Failed to create account")
        else:
            logger.error("❌ Failed to get domains")
            
    except Exception as e:
        logger.error(f"❌ Exception during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.close()
        logger.info("🔄 API client closed")

if __name__ == "__main__":
    asyncio.run(test_our_api())
