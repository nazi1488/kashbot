"""
Обработчик команды /start и начального взаимодействия
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.localization import get_text
import config

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', '/start')
    
    # Проверяем есть ли сохраненный язык пользователя
    saved_language = None
    if 'database' in context.bot_data:
        db = context.bot_data['database']
        saved_language = await db.get_user_language(user.id)
        logger.info(f"User {user.id} saved language: {saved_language}")
    
    if saved_language:
        # У пользователя уже есть сохраненный язык - устанавливаем его и переходим к главному меню
        context.user_data['language'] = saved_language
        logger.info(f"User {user.id} using saved language: {saved_language}")
        
        # Отправляем приветствие на сохраненном языке
        welcome_text = get_text(context, 'welcome_back')
        await update.message.reply_text(welcome_text)
        
        # Переходим сразу к проверке подписки (затем к главному меню)
        from .subscription import check_subscription_status
        await check_subscription_status(update, context)
    else:
        # Первый запуск - показываем выбор языка
        logger.info(f"User {user.id} - first time, showing language selection")
        
        # Создаем клавиатуру выбора языка
        keyboard = [
            [
                InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение с выбором языка
        await update.message.reply_text(
            "Оберіть мову / Choose language / Выберите язык:",
            reply_markup=reply_markup
        )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора языка"""
    query = update.callback_query
    await query.answer()
    
    # Получаем выбранный язык
    lang_code = query.data.split('_')[1]
    user = query.from_user
    
    # Сохраняем язык в user_data
    context.user_data['language'] = lang_code
    logger.info(f"User {user.id} selected language: {lang_code}")
    
    try:
        # Сохраняем язык в базу данных
        if 'database' in context.bot_data:
            db = context.bot_data['database']
            success = await db.set_user_language(user.id, lang_code, user.username)
            if success:
                logger.info(f"✅ Language {lang_code} saved for user {user.id}")
            else:
                logger.error(f"❌ Failed to save language for user {user.id}")
        
        # Отправляем подтверждение выбора языка
        selected_text = get_text(context, 'language_selected')
        logger.debug(f"Language selected text: {selected_text}")
        
        await query.edit_message_text(text=selected_text)
        
        # Переходим к проверке подписки
        from .subscription import check_subscription_status
        await check_subscription_status(update, context)
        
    except Exception as e:
        logger.error(f"Error in language_callback: {e}", exc_info=True)
        # Пытаемся отправить сообщение об ошибке
        try:
            await query.message.reply_text(
                "An error occurred. Please try /start again."
            )
        except:
            pass
