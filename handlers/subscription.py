"""
Обработчик проверки подписки на канал
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import check_subscription
from utils.localization import get_text
import config

logger = logging.getLogger(__name__)


async def check_subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет подписку пользователя и показывает соответствующее меню"""
    user = update.effective_user
    
    logger.info(f"Checking subscription for user {user.id} to channel {config.CHANNEL_USERNAME}")
    
    # Проверяем подписку
    is_subscribed = await check_subscription(
        context.bot,
        user.id,
        config.CHANNEL_USERNAME
    )
    
    if is_subscribed:
        # Если подписан, показываем главное меню
        await show_main_menu(update, context)
    else:
        # Если не подписан, показываем просьбу подписаться
        keyboard = [[
            InlineKeyboardButton(
                get_text(context, 'check_subscription'),
                callback_data='check_subscription'
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = get_text(
            context,
            'subscription_required',
            channel=config.CHANNEL_USERNAME
        )
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки проверки подписки"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    # Проверяем подписку
    is_subscribed = await check_subscription(
        context.bot,
        user.id,
        config.CHANNEL_USERNAME
    )
    
    if is_subscribed:
        # Подписка подтверждена
        await query.edit_message_text(
            text=get_text(context, 'subscription_verified')
        )
        # Показываем главное меню
        await show_main_menu(update, context)
    else:
        # Все еще не подписан
        keyboard = [[
            InlineKeyboardButton(
                get_text(context, 'check_subscription'),
                callback_data='check_subscription'
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=get_text(
                context,
                'subscription_required',
                channel=config.CHANNEL_USERNAME
            ),
            reply_markup=reply_markup
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню бота"""
    keyboard = [
        [InlineKeyboardButton(
            get_text(context, 'uniqueness_tool'),
            callback_data='uniqueness_tool'
        )],
        [InlineKeyboardButton(
            get_text(context, 'hide_text'),
            callback_data='hide_text'
        )],
        [InlineKeyboardButton(
            get_text(context, 'smart_compress'),
            callback_data='smart_compress'
        )],
        [InlineKeyboardButton(
            get_text(context, 'video_downloader'),
            callback_data='video_downloader'
        )],
        [InlineKeyboardButton(
            get_text(context, 'totp_generator'),
            callback_data='totp_menu'
        )],
        [InlineKeyboardButton(
            get_text(context, 'roi_calculator'),
            callback_data='roi_calculator'
        )],
        [InlineKeyboardButton(
            get_text(context, 'gmail_aliases'),
            callback_data='gmail_menu'
        )],
        [InlineKeyboardButton(
            "📩 Временная Почта",
            callback_data='kashmail_menu'
        )],
        [InlineKeyboardButton(
            "👤 Random Face",
            callback_data='random_face_menu'
        )],
        [InlineKeyboardButton(
            get_text(context, 'keitaro_menu'),
            callback_data='keitaro_menu'
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = get_text(context, 'welcome')
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
