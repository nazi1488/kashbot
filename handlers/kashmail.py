"""
Обработчики для KashMail - временная почта
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from services.kashmail_api import MailTmApi
from repos.kashmail_sessions import KashmailRepository
from utils.otp_extract import extract_codes, extract_links
from utils.localization import get_text
from database.models import Database
import config
import logging

logger = logging.getLogger(__name__)

# Константы для состояний ConversationHandler (если понадобятся)
WAITING_FOR_EMAIL_ACTION = 1


class KashmailHandler:
    """Основной класс для обработки KashMail"""
    
    def __init__(self):
        self.api = MailTmApi(timeout_seconds=30)
        self.active_watchers = {}  # user_id -> watcher_task
        
    async def cleanup(self):
        """Очистка ресурсов"""
        await self.api.close()
        
        # Останавливаем все активные наблюдатели
        for user_id, task in self.active_watchers.items():
            if task and not task.done():
                task.cancel()
        self.active_watchers.clear()


# Глобальный экземпляр
kashmail_handler = KashmailHandler()


async def kashmail_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню KashMail"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Получаем репозиторий
        if 'database' not in context.bot_data:
            await query.edit_message_text("❌ База данных недоступна")
            return
            
        db = context.bot_data['database']
        repo = KashmailRepository(db)
        
        # Проверяем активную сессию
        session = await repo.sessions.get_session(user_id)
        
        # Получаем дневной лимит из конфига
        daily_limit = getattr(config, 'KASHMAIL_DAILY_LIMIT', 10)
        remaining_quota = await repo.counters.get_remaining_quota(user_id, daily_limit)
        
        # Формируем текст меню
        menu_text = get_text(context, 'kashmail_menu_title')
        menu_text += f"\n\n📊 **{get_text(context, 'kashmail_quota')}:** {remaining_quota}/{daily_limit}"
        
        keyboard = []
        
        if session and session['status'] in ['active', 'waiting']:
            # Есть активная сессия
            address = session['address']
            status = session['status']
            
            menu_text += f"\n\n📧 **{get_text(context, 'kashmail_active_email')}:**\n`{address}`"
            menu_text += f"\n📊 **{get_text(context, 'kashmail_status')}:** {get_text(context, f'kashmail_status_{status}')}"
            
            # Кнопки для активной сессии БЕЗ копирования и ожидания
            keyboard.extend([
                [InlineKeyboardButton(get_text(context, 'kashmail_check_messages'), callback_data="kashmail_check")],
                [InlineKeyboardButton(get_text(context, 'kashmail_burn_address'), callback_data="kashmail_burn")]
            ])
        else:
            # Нет активной сессии
            if remaining_quota > 0:
                keyboard.append([InlineKeyboardButton(get_text(context, 'kashmail_generate_email'), callback_data="kashmail_generate")])
            else:
                menu_text += f"\n\n⚠️ {get_text(context, 'kashmail_quota_exceeded')}"
        
        # Общие кнопки
        keyboard.append([InlineKeyboardButton(get_text(context, 'back_to_menu'), callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in kashmail_menu_callback: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def kashmail_generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерация нового временного email"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Получаем репозиторий
        if 'database' not in context.bot_data:
            await query.edit_message_text("❌ База данных недоступна")
            return
            
        db = context.bot_data['database']
        repo = KashmailRepository(db)
        
        # Проверяем, может ли пользователь создать email
        daily_limit = getattr(config, 'KASHMAIL_DAILY_LIMIT', 10)
        can_create, reason = await repo.can_user_create_email(user_id, daily_limit)
        
        if not can_create:
            await query.edit_message_text(f"❌ {reason}")
            return
        
        # Показываем сообщение о создании
        loading_text = get_text(context, 'kashmail_generating')
        await query.edit_message_text(loading_text)
        
        # Создаем временный email
        result = await kashmail_handler.api.create_temporary_email()
        
        if not result:
            await query.edit_message_text(f"❌ {get_text(context, 'kashmail_generation_failed')}")
            return
        
        email, jwt_token, expires_at = result
        
        # Сохраняем сессию в БД
        success = await repo.create_new_email_session(user_id, email, jwt_token, expires_at)
        
        if not success:
            await query.edit_message_text(f"❌ {get_text(context, 'kashmail_save_failed')}")
            return
        
        # Сразу показываем статус-панель вместо сообщения о генерации
        await _show_kashmail_status_panel(query, context)
        
    except Exception as e:
        logger.error(f"Error in kashmail_generate_callback: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def _show_kashmail_status_panel(query, context):
    """Показать панель статуса KashMail без кнопки копирования"""
    user_id = query.from_user.id
    
    try:
        # Получаем базу данных из контекста
        if 'database' not in context.bot_data:
            await query.edit_message_text("❌ База данных недоступна")
            return
            
        db = context.bot_data['database']
        repo = KashmailRepository(db)
        
        # Проверяем активную сессию
        session = await repo.sessions.get_session(user_id)
        
        if not session:
            await query.edit_message_text("❌ Активная сессия не найдена")
            return
        
        # Получаем дневной лимит из конфига
        daily_limit = getattr(config, 'KASHMAIL_DAILY_LIMIT', 10)
        remaining_quota = await repo.counters.get_remaining_quota(user_id, daily_limit)
        
        # Формируем текст меню
        menu_text = get_text(context, 'kashmail_menu_title')
        menu_text += f"\n\n📊 **{get_text(context, 'kashmail_quota')}:** {remaining_quota}/{daily_limit}"
        
        address = session['address']
        status = session['status']
        
        menu_text += f"\n\n📧 **{get_text(context, 'kashmail_active_email')}:**\n`{address}`"
        menu_text += f"\n📊 **{get_text(context, 'kashmail_status')}:** {get_text(context, f'kashmail_status_{status}')}"
        
        # Кнопки для активной сессии БЕЗ кнопки копирования и ожидания
        keyboard = [
            [InlineKeyboardButton(get_text(context, 'kashmail_check_messages'), callback_data="kashmail_check")],
            [InlineKeyboardButton(get_text(context, 'kashmail_burn_address'), callback_data="kashmail_burn")],
            [InlineKeyboardButton(get_text(context, 'back_to_menu'), callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in _show_kashmail_status_panel: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def kashmail_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Копирование email адреса"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем email из callback_data
    email = query.data.replace("kashmail_copy_", "")
    
    copy_text = get_text(context, 'kashmail_copy_instruction')
    copy_text += f"\n\n`{email}`"
    copy_text += f"\n\n{get_text(context, 'kashmail_copy_hint')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(context, 'kashmail_back_to_menu'), callback_data="kashmail_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=copy_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def kashmail_wait_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск ожидания сообщений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Останавливаем предыдущий watcher если есть
        if user_id in kashmail_handler.active_watchers:
            old_task = kashmail_handler.active_watchers[user_id]
            if old_task and not old_task.done():
                old_task.cancel()
        
        # Получаем сессию
        if 'database' not in context.bot_data:
            await query.edit_message_text("❌ База данных недоступна")
            return
            
        db = context.bot_data['database']
        repo = KashmailRepository(db)
        
        session = await repo.sessions.get_session(user_id)
        if not session:
            await query.edit_message_text(f"❌ {get_text(context, 'kashmail_no_active_session')}")
            return
        
        jwt_token = session['jwt']
        address = session['address']
        
        # Обновляем статус на "waiting"
        await repo.sessions.update_session_status(user_id, 'waiting')
        
        # Показываем сообщение об ожидании
        wait_timeout = getattr(config, 'KASHMAIL_WAIT_TIMEOUT', 200)
        waiting_text = get_text(context, 'kashmail_waiting_started')
        waiting_text += f"\n\n📧 **Email:** `{address}`"
        waiting_text += f"\n⏱️ **{get_text(context, 'kashmail_timeout')}:** {wait_timeout} {get_text(context, 'seconds')}"
        waiting_text += f"\n\n{get_text(context, 'kashmail_waiting_instruction')}"
        
        keyboard = [
            [InlineKeyboardButton(get_text(context, 'kashmail_stop_waiting'), callback_data="kashmail_stop_wait")],
            [InlineKeyboardButton(get_text(context, 'kashmail_burn_address'), callback_data="kashmail_burn")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=waiting_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Запускаем асинхронное ожидание
        watcher = KashmailEmailWatcher(kashmail_handler.api)
        task = asyncio.create_task(
            _wait_for_messages(context, user_id, jwt_token, address, wait_timeout, query.message.chat_id)
        )
        kashmail_handler.active_watchers[user_id] = task
        
    except Exception as e:
        logger.error(f"Error in kashmail_wait_callback: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def _wait_for_messages(context, user_id: int, jwt_token: str, address: str, timeout: int, chat_id: int):
    """Асинхронное ожидание сообщений"""
    try:
        watcher = KashmailEmailWatcher(kashmail_handler.api)
        
        async def message_callback(messages):
            """Обработка полученных сообщений"""
            try:
                for message in messages:
                    await _send_message_notification(context, user_id, message, address, chat_id)
                
                # Обновляем статус сессии
                if 'database' in context.bot_data:
                    repo = KashmailRepository(context.bot_data['database'])
                    await repo.sessions.update_session_status(user_id, 'done')
                    
            except Exception as e:
                logger.error(f"Error in message callback: {e}")
        
        # Ожидаем сообщения
        messages = await watcher.watch_for_new_messages(
            jwt_token, 
            timeout_seconds=timeout,
            callback=message_callback
        )
        
        # Если таймаут без сообщений
        if messages is None:
            timeout_text = get_text(context, 'kashmail_timeout_reached')
            timeout_text += f"\n\n📧 **Email:** `{address}`"
            timeout_text += f"\n\n{get_text(context, 'kashmail_timeout_suggestion')}"
            
            keyboard = [
                [InlineKeyboardButton(get_text(context, 'kashmail_generate_new'), callback_data="kashmail_generate")],
                [InlineKeyboardButton(get_text(context, 'back_to_menu'), callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=timeout_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        
    except asyncio.CancelledError:
        logger.info(f"Message watching cancelled for user {user_id}")
    except Exception as e:
        logger.error(f"Error in _wait_for_messages: {e}")
    finally:
        # Убираем из активных наблюдателей
        if user_id in kashmail_handler.active_watchers:
            del kashmail_handler.active_watchers[user_id]


async def _send_message_notification(context, user_id: int, message, address: str, chat_id: int):
    """Отправка уведомления о новом сообщении"""
    try:
        from utils.otp_extract import extract_codes, extract_links
        
        # Формируем текст уведомления
        notification_text = f"📨 **{get_text(context, 'kashmail_new_message')}**\n\n"
        notification_text += f"📧 **To:** `{address}`\n"
        notification_text += f"📤 **From:** `{message.from_email}`\n"
        notification_text += f"📋 **Subject:** {message.subject}\n"
        notification_text += f"🕐 **Date:** {message.date.strftime('%H:%M %d.%m.%Y')}"
        
        # Извлекаем коды и ссылки
        text_content = message.text_content or ""
        html_content = message.html_content or ""
        full_content = f"{text_content} {html_content}"
        
        codes = extract_codes(full_content, message.subject)
        links = extract_links(html_content or text_content)
        
        if codes:
            notification_text += f"\n\n🔑 **{get_text(context, 'kashmail_codes_found')}:** `{codes[0]}`"
        
        # Создаем клавиатуру
        keyboard = []
        
        if text_content.strip():
            keyboard.append([InlineKeyboardButton(get_text(context, 'kashmail_show_body'), callback_data=f"kashmail_show_{message.id}")])
        
        if codes:
            keyboard.append([InlineKeyboardButton(get_text(context, 'kashmail_copy_code'), callback_data=f"kashmail_copy_code_{codes[0]}")])
        
        if links:
            keyboard.append([InlineKeyboardButton(get_text(context, 'kashmail_show_links'), callback_data=f"kashmail_links_{message.id}")])
        
        keyboard.extend([
            [InlineKeyboardButton(get_text(context, 'kashmail_burn_address'), callback_data="kashmail_burn")],
            [InlineKeyboardButton(get_text(context, 'kashmail_back_to_menu'), callback_data="kashmail_menu")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=notification_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error sending message notification: {e}")


async def kashmail_stop_wait_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка ожидания сообщений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Останавливаем watcher
    if user_id in kashmail_handler.active_watchers:
        task = kashmail_handler.active_watchers[user_id]
        if task and not task.done():
            task.cancel()
        del kashmail_handler.active_watchers[user_id]
    
    # Обновляем статус сессии
    if 'database' in context.bot_data:
        repo = KashmailRepository(context.bot_data['database'])
        await repo.sessions.update_session_status(user_id, 'active')
    
    stopped_text = get_text(context, 'kashmail_waiting_stopped')
    
    keyboard = [
        [InlineKeyboardButton(get_text(context, 'kashmail_back_to_menu'), callback_data="kashmail_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=stopped_text,
        reply_markup=reply_markup
    )


async def kashmail_burn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сжигание адреса"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Останавливаем watcher если есть
        if user_id in kashmail_handler.active_watchers:
            task = kashmail_handler.active_watchers[user_id]
            if task and not task.done():
                task.cancel()
            del kashmail_handler.active_watchers[user_id]
        
        # Сжигаем сессию в БД
        if 'database' in context.bot_data:
            repo = KashmailRepository(context.bot_data['database'])
            await repo.sessions.burn_session(user_id)
        
        burned_text = get_text(context, 'kashmail_address_burned')
        burned_text += f"\n\n{get_text(context, 'kashmail_burn_explanation')}"
        
        keyboard = [
            [InlineKeyboardButton(get_text(context, 'kashmail_generate_new'), callback_data="kashmail_generate")],
            [InlineKeyboardButton(get_text(context, 'back_to_menu'), callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=burned_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in kashmail_burn_callback: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def kashmail_check_messages_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка сообщений без ожидания"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Получаем сессию
        if 'database' not in context.bot_data:
            await query.edit_message_text("❌ База данных недоступна")
            return
            
        db = context.bot_data['database']
        repo = KashmailRepository(db)
        
        session = await repo.sessions.get_session(user_id)
        if not session:
            await query.edit_message_text(f"❌ {get_text(context, 'kashmail_no_active_session')}")
            return
        
        jwt_token = session['jwt']
        address = session['address']
        
        # Показываем индикатор загрузки
        await query.edit_message_text(get_text(context, 'kashmail_checking_messages'))
        
        # Получаем сообщения
        messages = await kashmail_handler.api.get_messages(jwt_token)
        
        if not messages:
            no_messages_text = get_text(context, 'kashmail_no_messages')
            no_messages_text += f"\n\n📧 **Email:** `{address}`"
            
            keyboard = [
                [InlineKeyboardButton(get_text(context, 'kashmail_back_to_menu'), callback_data="kashmail_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=no_messages_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Есть сообщения - показываем содержимое последнего письма
        latest_message = messages[0]  # API возвращает сообщения в порядке убывания даты
        
        # Получаем детали сообщения
        message_detail = await kashmail_handler.api.get_message_detail(latest_message['id'], jwt_token)
        
        if message_detail:
            await _show_message_content(query, context, message_detail, address)
        else:
            await query.edit_message_text(f"❌ {get_text(context, 'kashmail_message_load_failed')}")
        
    except Exception as e:
        logger.error(f"Error in kashmail_check_messages_callback: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def _show_message_content(query, context, message_detail, email_address):
    """Показать содержимое письма как в обычной почте"""
    try:
        # Извлекаем OTP коды и ссылки
        codes = extract_codes(message_detail.html_content or message_detail.text_content, message_detail.subject)
        links = extract_links(message_detail.html_content or message_detail.text_content)
        
        # Очищаем и форматируем текст
        from utils.otp_extract import clean_html
        clean_text = clean_html(message_detail.html_content or message_detail.text_content)
        
        # Создаем красивое отображение письма
        header = f"📧 **Новое письмо в {email_address}**\n\n"
        header += f"👤 **От:** {message_detail.from_email}\n"
        header += f"📋 **Тема:** {message_detail.subject}\n"
        header += f"📅 **Дата:** {message_detail.date.strftime('%H:%M %d.%m.%Y')}\n"
        
        # Добавляем найденные коды если есть
        if codes:
            header += f"\n🔑 **Найдены коды:** {', '.join(codes[:3])}"  # Показываем первые 3
        
        header += "\n" + "─" * 30 + "\n\n"
        
        # Ограничиваем длину текста для Telegram
        max_content_length = 4000 - len(header) - 200  # Оставляем место для кнопок
        
        if len(clean_text) > max_content_length:
            content = clean_text[:max_content_length] + "...\n\n📄 *Текст обрезан*"
        else:
            content = clean_text
            
        full_text = header + content
        
        # Создаем только навигационные кнопки
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить ещё", callback_data="kashmail_check")],
            [InlineKeyboardButton("◀️ Назад к Временной Почте", callback_data="kashmail_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=full_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in _show_message_content: {e}")
        await query.edit_message_text(f"❌ {get_text(context, 'error_occurred')}")


async def kashmail_show_body_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки показа тела письма"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    logger.info(f"kashmail_show_body_callback called with data: {callback_data}")
    
    # Извлекаем ID сообщения из callback_data: kashmail_show_{message_id}
    if not callback_data.startswith("kashmail_show_"):
        logger.error(f"Invalid callback data: {callback_data}")
        return
        
    message_id = callback_data.replace("kashmail_show_", "")
    
    try:
        # Получаем сессию пользователя
        db = Database()
        repo = KashmailRepository(db)
        session = await repo.sessions.get_session(user_id)
        
        if not session:
            await query.edit_message_text(
                text=get_text(context, 'kashmail_no_active_session')
            )
            return
        
        # Получаем детали сообщения
        api = MailTmApi()
        try:
            message = await api.get_message_detail(message_id, session['jwt'])
            
            if message:
                # Очищаем и форматируем текст
                from utils.otp_extract import clean_html
                clean_text = clean_html(message.html_content or message.text_content)
                
                # Ограничиваем длину для Telegram
                max_length = 4000
                if len(clean_text) > max_length:
                    clean_text = clean_text[:max_length] + "...\n\n📄 Текст обрезан из-за ограничений Telegram"
                
                # Создаем кнопку "Назад"
                keyboard = [[
                    InlineKeyboardButton(
                        get_text(context, 'back'), 
                        callback_data='kashmail_menu'
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=f"📄 **Тело письма**\n\n{clean_text}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    text=get_text(context, 'kashmail_message_load_failed')
                )
        finally:
            await api.close()
            
    except Exception as e:
        logger.error(f"Error showing message body: {e}")
        await query.edit_message_text(
            text=get_text(context, 'error_occurred')
        )


async def kashmail_show_links_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки показа ссылок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    logger.info(f"kashmail_show_links_callback called with data: {callback_data}")
    
    # Извлекаем ID сообщения из callback_data: kashmail_links_{message_id}
    if not callback_data.startswith("kashmail_links_"):
        logger.error(f"Invalid callback data: {callback_data}")
        return
        
    message_id = callback_data.replace("kashmail_links_", "")
    
    try:
        # Получаем сессию пользователя
        db = Database()
        repo = KashmailRepository(db)
        session = await repo.sessions.get_session(user_id)
        
        if not session:
            await query.edit_message_text(
                text=get_text(context, 'kashmail_no_active_session')
            )
            return
        
        # Получаем детали сообщения
        api = MailTmApi()
        try:
            message = await api.get_message_detail(message_id, session['jwt'])
            
            if message:
                # Извлекаем ссылки
                from utils.otp_extract import extract_links
                links = extract_links(message.html_content or message.text_content)
                
                if links:
                    links_text = "\n".join([f"🔗 {link}" for link in links[:10]])  # Показываем первые 10
                    if len(links) > 10:
                        links_text += f"\n\n... и еще {len(links) - 10} ссылок"
                        
                    text = f"🔗 **Ссылки из письма**\n\n{links_text}"
                else:
                    text = "🔗 **Ссылки из письма**\n\nСсылки не найдены"
                
                # Создаем кнопку "Назад"
                keyboard = [[
                    InlineKeyboardButton(
                        get_text(context, 'back'), 
                        callback_data='kashmail_menu'
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    text=get_text(context, 'kashmail_message_load_failed')
                )
        finally:
            await api.close()
            
    except Exception as e:
        logger.error(f"Error showing message links: {e}")
        await query.edit_message_text(
            text=get_text(context, 'error_occurred')
        )


# Функция очистки для корректного завершения
async def cleanup_kashmail():
    """Очистка ресурсов KashMail при завершении бота"""
    await kashmail_handler.cleanup()
