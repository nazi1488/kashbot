"""
Обработчик для скрытия текста с помощью Zero-Width Space
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from utils.localization import get_text
from utils.text_utils import hide_text_with_zwsp

logger = logging.getLogger(__name__)

# Состояние для ConversationHandler
WAITING_FOR_TEXT = 0


async def hide_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Скрыть текст'"""
    query = update.callback_query
    await query.answer()
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', 'hide_text')
    
    # Отправляем объяснение
    await query.message.reply_text(
        text=get_text(context, 'hide_text_explanation'),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Показываем кнопку отмены
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Просим отправить текст
    await query.message.reply_text(
        text=get_text(context, 'send_text_to_hide'),
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_TEXT


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик полученного текста"""
    message = update.message
    text = message.text
    
    if not text or text.strip() == '':
        await message.reply_text(
            text=get_text(context, 'error_text_empty')
        )
        return WAITING_FOR_TEXT
    
    try:
        # Применяем скрытие текста
        hidden_text = hide_text_with_zwsp(text)
        
        # Отправляем результат в виде кода для удобного копирования
        result_message = get_text(context, 'hidden_text_result', text=hidden_text)
        
        await message.reply_text(
            text=result_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Показываем главное меню
        keyboard = [[
            InlineKeyboardButton(get_text(context, 'hide_text'), callback_data='hide_text'),
            InlineKeyboardButton(get_text(context, 'main_menu'), callback_data='main_menu')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            text=get_text(context, 'hide_text_more_or_menu'),
            reply_markup=reply_markup
        )
        
        logger.info(f"Successfully hidden text for user {message.from_user.id}, length: {len(text)}")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error hiding text: {e}")
        await message.reply_text(
            text=get_text(context, 'error_processing')
        )
        return ConversationHandler.END
