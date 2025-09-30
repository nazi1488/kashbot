"""
Утилита для проверки подписки пользователя на канал
"""

import logging
from telegram import Bot
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from typing import Optional

logger = logging.getLogger(__name__)


async def check_subscription(bot: Bot, user_id: int, channel_username: str) -> bool:
    """
    Проверяет, подписан ли пользователь на указанный канал
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя для проверки
        channel_username: Username канала (с @ или без)
    
    Returns:
        bool: True если подписан, False если нет
    """
    # Если канал не указан или пустой, пропускаем проверку
    if not channel_username or channel_username in ['@channel_username', '']:
        logger.info("Channel username not configured, skipping subscription check")
        return True
        
    try:
        # Убедимся, что username начинается с @
        if not channel_username.startswith('@'):
            channel_username = f'@{channel_username}'
        
        # Проверяем, что это не ссылка
        if channel_username.startswith('@https://') or 'https://' in channel_username:
            logger.error(f"Invalid channel username format: {channel_username}. Use @username format instead of link")
            return True  # Пропускаем проверку при неправильном формате
        
        # Получаем информацию о статусе пользователя в канале
        member = await bot.get_chat_member(channel_username, user_id)
        
        # Проверяем статус
        if member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ]:
            logger.info(f"User {user_id} is subscribed to {channel_username}")
            return True
        else:
            logger.info(f"User {user_id} is NOT subscribed to {channel_username} (status: {member.status})")
            return False
            
    except TelegramError as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        # В случае ошибки (например, бот не админ в канале) разрешаем доступ
        return True
    except Exception as e:
        logger.error(f"Unexpected error checking subscription: {e}")
        return True


async def ensure_bot_can_check_subscription(bot: Bot, channel_username: str) -> Optional[str]:
    """
    Проверяет, может ли бот проверять подписки в канале
    
    Args:
        bot: Экземпляр бота
        channel_username: Username канала
    
    Returns:
        Optional[str]: Сообщение об ошибке или None если всё в порядке
    """
    try:
        if not channel_username.startswith('@'):
            channel_username = f'@{channel_username}'
        
        # Пытаемся получить информацию о канале
        chat = await bot.get_chat(channel_username)
        
        # Проверяем, является ли бот администратором
        bot_member = await bot.get_chat_member(channel_username, bot.id)
        
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return f"Bot must be administrator in {channel_username} to check subscriptions"
        
        return None
        
    except TelegramError as e:
        return f"Cannot access channel {channel_username}: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
