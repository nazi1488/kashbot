"""
Telegram handlers для настройки интеграции с Keitaro
"""

import secrets
import logging
from typing import Dict, Any
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

from database import Database
from utils.localization import get_text
from features.keitaro.templates import get_test_message

logger = logging.getLogger(__name__)


# Состояния FSM
class KeitaroStates(Enum):
    MAIN_MENU = 0
    SETUP_PROFILE = 1
    INPUT_CHAT_ID = 2
    INPUT_TOPIC_ID = 3
    ROUTES_MENU = 4
    ADD_ROUTE = 5
    INPUT_ROUTE_VALUE = 6
    INPUT_ROUTE_CHAT = 7
    INPUT_ROUTE_TOPIC = 8
    INPUT_ROUTE_FILTERS = 9
    LIMITS_MENU = 10
    INPUT_RATE_LIMIT = 11
    INPUT_DEDUP_TTL = 12
    PULL_MENU = 13
    INPUT_PULL_URL = 14
    INPUT_PULL_KEY = 15
    INPUT_PULL_FILTERS = 16


class KeitaroHandlers:
    """Обработчики для настройки интеграции с Keitaro"""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает главное меню Keitaro"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Проверяем есть ли профиль
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            # Профиля нет - предлагаем создать
            text = get_text(context, 'keitaro_welcome')
            keyboard = [
                [InlineKeyboardButton(
                    get_text(context, 'keitaro_create_profile'),
                    callback_data='keitaro_create'
                )],
                [InlineKeyboardButton(
                    get_text(context, 'back_to_menu'),
                    callback_data='main_menu'
                )]
            ]
        else:
            # Профиль есть - показываем настройки
            domain = context.bot_data.get('webhook_domain', 'YOUR_DOMAIN')
            # Убираем дубликат https:// если domain уже содержит протокол
            if domain.startswith('http'):
                postback_url = f"{domain}/integrations/keitaro/postback?secret={profile['secret']}"
            else:
                postback_url = f"https://{domain}/integrations/keitaro/postback?secret={profile['secret']}"
            
            status = "✅" if profile['enabled'] else "❌"
            
            text = get_text(context, 'keitaro_profile_info').format(
                status=status,
                url=postback_url,
                chat_id=profile['default_chat_id'],
                topic_id=profile['default_topic_id'] or 'N/A'
            )
            
            keyboard = [
                [InlineKeyboardButton(
                    get_text(context, 'keitaro_test'),
                    callback_data='keitaro_test'
                )],
                [InlineKeyboardButton(
                    get_text(context, 'keitaro_howto'),
                    callback_data='keitaro_howto'
                )],
                [InlineKeyboardButton(
                    get_text(context, 'keitaro_toggle'),
                    callback_data='keitaro_toggle'
                )],
                [InlineKeyboardButton(
                    get_text(context, 'back_to_menu'),
                    callback_data='main_menu'
                )]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
        
        return KeitaroStates.MAIN_MENU.value
    
    async def create_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Создает новый профиль Keitaro"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Генерируем секретный ключ
        import secrets
        secret = secrets.token_urlsafe(32)
        
        # Автоматически используем чат с ботом (user_id как chat_id)
        setup_data = {
            'owner_user_id': user_id,
            'secret': secret,
            'default_chat_id': user_id,  # Всегда используем чат с ботом
            'default_topic_id': None
        }
        
        # Сохраняем профиль сразу
        await self._save_profile(setup_data)
        
        # Показываем созданный профиль
        context.user_data['keitaro_setup'] = setup_data
        return await self.show_profile_created(update, context)
    
    async def select_this_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Использует текущий чат для отправки"""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat_id
        setup_data = context.user_data.get('keitaro_setup', {})
        setup_data['default_chat_id'] = chat_id
        
        # Проверяем, есть ли топики в этом чате
        if query.message.chat.type == 'supergroup':
            text = get_text(context, 'keitaro_input_topic')
            keyboard = [
                [InlineKeyboardButton(
                    get_text(context, 'keitaro_no_topic'),
                    callback_data='keitaro_no_topic'
                )]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
            return KeitaroStates.INPUT_TOPIC_ID.value
        else:
            # Сохраняем профиль
            await self._save_profile(setup_data)
            return await self.show_profile_created(update, context)
    
    async def input_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Запрашивает ввод chat_id"""
        query = update.callback_query
        await query.answer()
        
        text = get_text(context, 'keitaro_input_chat_id')
        
        keyboard = [[InlineKeyboardButton(
            get_text(context, 'cancel'),
            callback_data='keitaro_menu'
        )]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        return KeitaroStates.INPUT_CHAT_ID.value
    
    async def handle_chat_id_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает введенный chat_id"""
        try:
            chat_id = int(update.message.text.strip())
            
            # Проверяем доступ к чату
            try:
                chat = await context.bot.get_chat(chat_id)
                chat_name = chat.title or chat.username or str(chat_id)
            except:
                await update.message.reply_text(get_text(context, 'keitaro_invalid_chat'))
                return KeitaroStates.INPUT_CHAT_ID.value
            
            setup_data = context.user_data.get('keitaro_setup', {})
            setup_data['default_chat_id'] = chat_id
            
            # Сохраняем профиль
            await self._save_profile(setup_data)
            return await self.show_profile_created(update, context)
            
        except ValueError:
            await update.message.reply_text(get_text(context, 'keitaro_invalid_chat'))
            return KeitaroStates.INPUT_CHAT_ID.value
    
    async def show_profile_created(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает информацию о созданном профиле"""
        setup_data = context.user_data.get('keitaro_setup', {})
        domain = context.bot_data.get('webhook_domain', 'YOUR_DOMAIN')
        # Убираем дубликат https:// если domain уже содержит протокол
        if domain.startswith('http'):
            postback_url = f"{domain}/integrations/keitaro/postback?secret={setup_data['secret']}"
        else:
            postback_url = f"https://{domain}/integrations/keitaro/postback?secret={setup_data['secret']}"
        
        text = get_text(context, 'keitaro_profile_created').format(url=postback_url)
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(context, 'keitaro_howto'),
                callback_data='keitaro_howto'
            )],
            [InlineKeyboardButton(
                get_text(context, 'back'),
                callback_data='keitaro_menu'
            )]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
        
        # Очищаем временные данные
        context.user_data.pop('keitaro_setup', None)
        
        return KeitaroStates.MAIN_MENU.value
    
    async def copy_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отправляет URL для копирования"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            await query.answer(get_text(context, 'keitaro_no_profile'), show_alert=True)
            return KeitaroStates.MAIN_MENU.value
        
        domain = context.bot_data.get('webhook_domain', 'YOUR_DOMAIN')
        # Убираем дубликат https:// если domain уже содержит протокол
        if domain.startswith('http'):
            postback_url = f"{domain}/integrations/keitaro/postback?secret={profile['secret']}"
        else:
            postback_url = f"https://{domain}/integrations/keitaro/postback?secret={profile['secret']}"
        
        # Отправляем URL отдельным сообщением для удобного копирования
        await query.message.reply_text(f"`{postback_url}`", parse_mode='Markdown')
        await query.answer(get_text(context, 'keitaro_url_sent'))
        
        return KeitaroStates.MAIN_MENU.value
    
    async def send_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отправляет тестовое сообщение"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            await query.answer(get_text(context, 'keitaro_no_profile'), show_alert=True)
            return KeitaroStates.MAIN_MENU.value
        
        try:
            # Отправляем тестовое сообщение
            test_message = get_test_message()
            
            if profile['default_topic_id']:
                await context.bot.send_message(
                    chat_id=profile['default_chat_id'],
                    message_thread_id=profile['default_topic_id'],
                    text=test_message,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    chat_id=profile['default_chat_id'],
                    text=test_message,
                    parse_mode='HTML'
                )
            
            await query.answer(get_text(context, 'keitaro_test_sent'), show_alert=True)
            
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            await query.answer(get_text(context, 'keitaro_test_failed'), show_alert=True)
        
        return KeitaroStates.MAIN_MENU.value
    
    async def show_howto(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает инструкцию по настройке"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if profile:
            domain = context.bot_data.get('webhook_domain', 'YOUR_DOMAIN')
            # Убираем дубликат https:// если domain уже содержит протокол
            if domain.startswith('http'):
                postback_url = f"{domain}/integrations/keitaro/postback?secret={profile['secret']}"
            else:
                postback_url = f"https://{domain}/integrations/keitaro/postback?secret={profile['secret']}"
        else:
            postback_url = "[Создайте профиль для получения URL]"
        
        text = get_text(context, 'keitaro_howto_text').format(url=postback_url)
        
        keyboard = [[InlineKeyboardButton(
            get_text(context, 'back'),
            callback_data='keitaro_menu'
        )]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        
        return KeitaroStates.MAIN_MENU.value
    
    async def toggle_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Включает/выключает профиль"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            await query.answer(get_text(context, 'keitaro_no_profile'), show_alert=True)
            return KeitaroStates.MAIN_MENU.value
        
        # Переключаем статус
        new_status = not profile['enabled']
        
        query_sql = """
            UPDATE keitaro_profiles 
            SET enabled = %s, updated_at = NOW()
            WHERE owner_user_id = %s
        """
        await self.db.execute(query_sql, (new_status, user_id))
        
        status_text = get_text(context, 'keitaro_enabled' if new_status else 'keitaro_disabled')
        await query.answer(status_text, show_alert=True)
        
        # Обновляем меню
        return await self.show_menu(update, context)
    
    async def _get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Получает профиль пользователя"""
        query = """
            SELECT * FROM keitaro_profiles 
            WHERE owner_user_id = %s 
            LIMIT 1
        """
        result = await self.db.execute(query, (user_id,), fetch=True)
        return result[0] if result else None
    
    async def show_routes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает меню маршрутизации"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            await query.answer(get_text(context, 'keitaro_no_profile'), show_alert=True)
            return KeitaroStates.MAIN_MENU.value
        
        # Получаем правила маршрутизации
        routes_query = """
            SELECT * FROM keitaro_routes 
            WHERE profile_id = %s 
            ORDER BY priority ASC, id ASC
            LIMIT 10
        """
        routes = await self.db.execute(routes_query, (profile['id'],), fetch=True)
        
        text = "🔀 **Правила маршрутизации**\n\n"
        
        if routes:
            for i, route in enumerate(routes, 1):
                text += f"{i}. {route['match_by']}: `{route['match_value']}`\n"
                text += f"   → Чат: `{route['target_chat_id']}`\n"
                if route['status_filter']:
                    text += f"   Фильтр: {route['status_filter']}\n"
                text += "\n"
        else:
            text += "Правил пока нет. Все события идут в чат по умолчанию.\n"
        
        text += "\n💡 Правила проверяются по порядку сверху вниз"
        
        keyboard = [
            [InlineKeyboardButton(
                "➕ Добавить правило",
                callback_data='keitaro_add_route'
            )],
            [InlineKeyboardButton(
                get_text(context, 'back'),
                callback_data='keitaro_menu'
            )]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return KeitaroStates.ROUTES_MENU.value
    
    async def show_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Показывает настройки лимитов"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        profile = await self._get_user_profile(user_id)
        
        if not profile:
            await query.answer(get_text(context, 'keitaro_no_profile'), show_alert=True)
            return KeitaroStates.MAIN_MENU.value
        
        text = f"""⚙️ **Лимиты и защита**

**Rate Limit:** {profile['rate_limit_rps']} запросов/сек
*Максимальное количество событий в секунду*

**Дедупликация:** {profile['dedup_ttl_sec']} сек
*Игнорирование повторных событий в течение этого времени*

📊 Рекомендуемые значения:
• Rate limit: 20-30 RPS
• Дедупликация: 3600 сек (1 час)"""
        
        keyboard = [
            [InlineKeyboardButton(
                "🔄 Изменить rate limit",
                callback_data='keitaro_change_rate'
            )],
            [InlineKeyboardButton(
                "⏰ Изменить дедупликацию",
                callback_data='keitaro_change_dedup'
            )],
            [InlineKeyboardButton(
                get_text(context, 'back'),
                callback_data='keitaro_menu'
            )]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return KeitaroStates.LIMITS_MENU.value
    
    async def _handle_main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает переход в главное меню"""
        query = update.callback_query
        if query:
            await query.answer()
        return ConversationHandler.END

    async def _save_profile(self, setup_data: Dict[str, Any]) -> None:
        """Сохраняет профиль в БД"""
        query = """
            INSERT INTO keitaro_profiles (
                owner_user_id, secret, default_chat_id, default_topic_id,
                enabled, rate_limit_rps, dedup_ttl_sec, pull_enabled,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (owner_user_id) DO UPDATE SET
                secret = EXCLUDED.secret,
                default_chat_id = EXCLUDED.default_chat_id,
                default_topic_id = EXCLUDED.default_topic_id,
                updated_at = NOW()
        """
        
        await self.db.execute(query, (
            setup_data['owner_user_id'],
            setup_data['secret'],
            setup_data['default_chat_id'],
            setup_data.get('default_topic_id'),
            True,   # enabled
            27,     # rate_limit_rps
            3600,   # dedup_ttl_sec
            False   # pull_enabled
        ))


def register_keitaro_handlers(application, database: Database):
    """Регистрирует handlers для Keitaro интеграции"""
    handlers = KeitaroHandlers(database)
    
    # Conversation handler для настройки
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.show_menu, pattern='^keitaro_menu$'),
        ],
        states={
            KeitaroStates.MAIN_MENU.value: [
                CallbackQueryHandler(handlers.create_profile, pattern='^keitaro_create$'),
                CallbackQueryHandler(handlers.send_test, pattern='^keitaro_test$'),
                CallbackQueryHandler(handlers.show_howto, pattern='^keitaro_howto$'),
                CallbackQueryHandler(handlers.toggle_profile, pattern='^keitaro_toggle$'),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handlers.show_menu, pattern='^keitaro_menu$'),
            CallbackQueryHandler(handlers._handle_main_menu_callback, pattern='^main_menu$'),
        ],
        per_user=True
    )
    
    application.add_handler(conv_handler)
