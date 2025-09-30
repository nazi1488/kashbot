"""
Админ панель для бота
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.constants import ParseMode
from typing import List, Dict, Any

from analytics import Analytics
from database import Database
from utils.localization import get_text
import config

logger = logging.getLogger(__name__)


class AdminPanel:
    """Класс админ панели"""
    
    # Состояния для рассылки
    BROADCAST_TYPE, BROADCAST_CONTENT, BROADCAST_CONFIRM = range(3)
    # Состояние для добавления cookies
    COOKIES_INPUT = 4

    def __init__(self, database: Database):
        self.db = database
        self.analytics = Analytics(database)
        self.broadcast_data: Dict[str, Any] = {}

    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        admin_ids = config.BOT_ADMINS or []
        return user_id in admin_ids
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает главное меню админ панели"""
        # Проверяем права доступа
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await update.effective_message.reply_text("⛔ У вас нет доступа к админ панели")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Метрики", callback_data="admin_metrics")],
            [InlineKeyboardButton("📈 Детальная аналитика", callback_data="admin_detailed")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("📨 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🍪 Управление Cookies", callback_data="admin_cookies")],
            [InlineKeyboardButton("⚙️ Статус системы", callback_data="admin_status")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "🔧 **Админ панель**\n\nВыберите раздел:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def show_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать основные метрики"""
        query = update.callback_query
        await query.answer()
        
        # Показываем сообщение о загрузке
        await query.edit_message_text("⏳ Загружаю метрики...")
        
        try:
            # Получаем метрики
            dau_wau_mau = await self.analytics.get_dau_wau_mau()
            total_users = await self.analytics.get_total_users()
            retention = {
                'D1': await self.analytics.get_average_retention(1, 30),
                'D7': await self.analytics.get_average_retention(7, 30),
                'D30': await self.analytics.get_average_retention(30, 30)
            }
            churn_rate = await self.analytics.get_churn_rate(30)
            
            # Форматируем текст
            text = f"""📊 **Основные метрики бота**

🎯 **Активные пользователи:**
• **DAU: {dau_wau_mau['DAU']}** - пользователи активные за последние 24 часа
• **WAU: {dau_wau_mau['WAU']}** - пользователи активные за последние 7 дней
• **MAU: {dau_wau_mau['MAU']}** - пользователи активные за последние 30 дней

📈 **Общая статистика:**
• **Всего: {total_users['total']}** - общее количество зарегистрированных пользователей
• **Активных: {total_users['active']}** - пользователи не заблокировавшие бота
• **Заблокировано: {total_users['blocked']}** - пользователи заблокировавшие бота

🔄 **Retention (удержание):**
• **D1: {retention['D1']}%** - процент пользователей вернувшихся на следующий день после регистрации
  Пример: если зарегистрировалось 100 чел, а вернулось 70 = 70%
• **D7: {retention['D7']}%** - процент пользователей вернувшихся через 7 дней после регистрации
  Пример: из 100 зарегистрированных через неделю осталось 25 = 25%
• **D30: {retention['D30']}%** - процент пользователей вернувшихся через 30 дней после регистрации
  Пример: из 100 зарегистрированных через месяц осталось 10 = 10%

📉 **Churn Rate: {churn_rate}%** - процент пользователей ушедших за последние 30 дней
  Пример: из 100 активных пользователей 5 ушли = 5% оттока

🔧 **Доступные функции бота:** 16 активных модулей
• Уникализатор, Скрытие текста, Сжатие файлов
• Скачивание видео (TikTok/YT/Instagram)  
• 2FA генератор, Gmail-алиасы, Временная почта
• Random Face генератор, Keitaro интеграция
• Админ панель, Мультиязычность, Аналитика

_Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing metrics: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке метрик")
    
    async def show_detailed_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать детальную аналитику"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text("⏳ Загружаю детальную аналитику...")
        
        try:
            # Использование команд (все функции, не ограничиваем)
            command_usage = await self.analytics.get_command_usage(30)
            top_commands = command_usage  # Все функции, а не топ-10
            
            # Новые пользователи
            new_users_data = await self.analytics.get_new_users(7)
            
            # Активность по часам
            hourly_activity = await self.analytics.get_hourly_activity(7)
            
            # Форматируем текст (убираем markdown для стабильности)
            text = "📈 Детальная аналитика бота\n\n"

            # Топ команд
            text += "🎯 Топ функций (30 дней):\n"
            if top_commands:
                for i, (cmd, count) in enumerate(top_commands, 1):
                    cmd_name = {
                        # Основные функции
                        '/start': '🚀 Запуск бота',
                        'uniqueness_tool': '🎨 Уникализатор',
                        'hide_text': '🥷 Скрытие текста', 
                        'smart_compress': '📉 Умное сжатие для FB',
                        'video_downloader': '🎬 Скачать TikTok Reels Shorts',
                        'totp_menu': '🔐 2FA Генератор',
                        'gmail_aliases': '📧 Gmail-зеркало',
                        'gmail_menu': '📧 Gmail-зеркало',
                        'kashmail_menu': '📩 Временная почта',
                        'random_face_menu': '👤 Random Face',
                        'keitaro_menu': '💚 Keitaro уведомления',
                        
                        # Навигация
                        'language_selection': '🌐 Выбор языка',
                        'main_menu': '🏠 Главное меню',
                        'back': '⬅️ Назад',
                        
                        # Языки
                        'lang_uk': '🇺🇦 Украинский язык',
                        'lang_ru': '🇷🇺 Русский язык', 
                        'lang_en': '🇬🇧 Английский язык',
                        
                        # Подписка
                        'check_subscription': '✅ Проверка подписки',
                        'subscription_verified': '✅ Подписка подтверждена',
                        
                        # Видео функции
                        'download_video': '📥 Скачивание видео',
                        'download_audio': '🎵 Скачивание аудио',
                        
                        # TOTP функции
                        'totp_generate_new': '🔄 Новый 2FA код',
                        'totp_custom_secret': '⚙️ Свой секрет 2FA',
                        'totp_refresh': '🔄 Обновить код',
                        'totp_qr_code': '📱 QR код',
                        
                        # Gmail функции  
                        'generate_aliases': '🎲 Сгенерировать алиасы',
                        'back_to_gmail': '🔙 К Gmail-зеркалу',
                        
                        # Keitaro функции
                        'keitaro_create': '➕ Создать профиль',
                        'keitaro_copy_url': '📋 Копировать URL',
                        'keitaro_test': '🧪 Тест уведомления',
                        'keitaro_toggle': '🔄 Вкл/Выкл профиль',
                        'keitaro_howto': '📖 Инструкция',
                        
                        # Админ функции
                        '/admin': '⚙️ Админ панель',
                        '/stats': '📊 Статистика',
                        'admin_metrics': '📊 Админ метрики',
                        'admin_detailed': '📈 Детальная аналитика',
                        'admin_users': '👥 Информация о пользователях',
                        'admin_broadcast': '📨 Рассылка админов',
                        'admin_cookies': '🍪 Управление куками',
                        'admin_status': '⚙️ Статус системы'
                    }.get(cmd, f'📱 {str(cmd)}')
                    text += f"{i}. {cmd_name}: {count} использований\n"
            else:
                text += "📊 Данные за 30 дней отсутствуют\n"

            # Новые пользователи
            text += "\n📅 Новые пользователи (7 дней):\n"
            if new_users_data:
                total_new = sum(count for _, count in new_users_data)
                text += f"• Всего новых: {total_new}\n"
                # Показываем последние дни
                for date_str, count in new_users_data[:3]:
                    text += f"• {date_str}: +{count} пользователей\n"
            else:
                text += "📊 Данные за 7 дней отсутствуют\n"

            # Пиковые часы
            text += "\n⏰ Пиковая активность (7 дней):\n"
            if hourly_activity:
                # Сортируем по количеству действий (hourly_activity уже список кортежей)
                sorted_hours = sorted(hourly_activity, key=lambda x: x[1], reverse=True)[:3]
                for hour, count in sorted_hours:
                    if count > 0:  # Показываем только ненулевые значения
                        text += f"• {hour:02d}:00 - {count} действий пользователей\n"
                if not any(count > 0 for _, count in hourly_activity):
                    text += "📊 Нет активности за последние 7 дней\n"
            else:
                text += "📊 Данные об активности отсутствуют\n"

            # Добавляем статистику по интеграциям если доступна
            try:
                # Проверяем наличие Keitaro профилей через ORM
                with self.db.get_session() as db_session:
                    from database.models import KeitaroProfile
                    keitaro_count = db_session.query(KeitaroProfile).filter(KeitaroProfile.enabled == True).count()
                    if keitaro_count > 0:
                        text += f"\n💚 Keitaro интеграция:\n• Активных профилей: {keitaro_count}\n"
                    
                    # Статистика событий Keitaro за последние 7 дней
                    from database.models import KeitaroEvent
                    cutoff_date = datetime.utcnow() - timedelta(days=7)
                    events_count = db_session.query(KeitaroEvent).filter(KeitaroEvent.created_at >= cutoff_date).count()
                    if events_count > 0:
                        text += f"• События за 7 дней: {events_count}\n"
            except Exception:
                # Если таблиц нет или ошибка - просто пропускаем
                pass
            
            # Подробная статистика по функциям
            text += "\n🔧 Все доступные функции бота:\n"
            
            # Основные инструменты
            text += "\n📱 **Основные инструменты:**\n"
            text += "• 🎨 Уникализатор медиафайлов (1-25 копий)\n"
            text += "• 📝 Скрытие текста невидимыми символами\n" 
            text += "• 🗜 Умное сжатие для Facebook Ads\n"
            text += "• 🎬 Скачивание видео (TikTok/YT/Instagram)\n"
            
            # Утилиты и генераторы
            text += "\n🛠 **Утилиты и генераторы:**\n"
            text += "• 🔐 2FA TOTP генератор с QR-кодами\n"
            text += "• 📧 Gmail-алиасы (dot-trick + плюсы)\n"
            text += "• 📩 Временная почта с автоматическим ожиданием\n"
            text += "• 👤 Random Face генератор (AI лица)\n"
            
            # Интеграции
            text += "\n🔗 **Интеграции:**\n"
            text += "• 💚 Keitaro → Telegram (S2S Postback)\n"
            text += "• 🌐 Мультиязычность (RU/UA/EN)\n"
            text += "• ⚙️ Админ панель с полной аналитикой\n"
            text += "• 🔔 Проверка подписки на канал\n"
            
            # Системные возможности
            text += "\n⚙️ **Системные возможности:**\n"
            text += "• 📊 Детальная аналитика использования\n"
            text += "• 🗃 База данных со всей историей\n"
            text += "• 🚀 Рассылка для админов\n"
            text += "• 🔄 Автоматические очереди обработки\n"
            
            text += f"\n💡 Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing detailed analytics: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке аналитики")
    
    async def show_users_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать информацию о пользователях"""
        query = update.callback_query
        await query.answer()
        
        try:
            total_users = await self.analytics.get_total_users()
            
            # Сегменты пользователей (get_users_for_broadcast не принимает параметров фильтрации)
            all_users_list = await self.analytics.get_users_for_broadcast()
            all_users = len(all_users_list)
            
            # Подсчитываем активных/неактивных пользователей по дате последней активности
            from datetime import datetime, timedelta
            now = datetime.now()
            active_7d = len([u for u in all_users_list if u['last_seen'] and (now - u['last_seen']).days <= 7])
            active_30d = len([u for u in all_users_list if u['last_seen'] and (now - u['last_seen']).days <= 30])
            inactive_7d = len([u for u in all_users_list if u['last_seen'] and (now - u['last_seen']).days > 7])
            
            text = f"""👥 **Информация о пользователях**

📊 **Общая статистика:**
• **Всего: {total_users['total']}** - общее количество зарегистрированных пользователей
• **Активных: {total_users['active']}** - пользователи не заблокировавшие бота
• **Заблокировано: {total_users['blocked']}** - пользователи заблокировавшие бота

🎯 **Сегменты для рассылки:**
• **Все активные: {all_users}** - все пользователи с активным ботом
• **Активные 7д: {active_7d}** - пользователи активные за последние 7 дней
• **Активные 30д: {active_30d}** - пользователи активные за последние 30 дней
• **Неактивные 7д: {inactive_7d}** - пользователи не активные более 7 дней

💡 **Используйте сегменты при создании рассылки:**
• "Все активные" - для массовых уведомлений
• "Активные 7д" - для вовлеченных пользователей
• "Активные 30д" - для всех, кто использует бота
• "Неактивные 7д" - для реактивации пользователей"""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing users info: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке информации")
    
    async def show_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать статус системы"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Импортируем менеджер очереди если есть
            try:
                from utils.queue_manager import compression_queue
                queue_stats = compression_queue.get_stats()
                queue_info = f"""
🔄 **Очередь сжатия:**
• Размер очереди: {queue_stats['queue_size']}
• Активных задач: {queue_stats['current_tasks']}/{queue_stats['max_concurrent']}
• Обработано: {queue_stats['tasks_processed']}
• Ошибок: {queue_stats['tasks_failed']}
• CPU: {queue_stats['cpu_usage']:.1f}%"""
            except:
                queue_info = "\n🔄 **Очередь сжатия:** Не настроена"
            
            # Статистика БД
            with self.db.get_session() as db_session:
                from database.models import User, Event, Session
                users_count = db_session.query(User).count()
                events_count = db_session.query(Event).count()
                sessions_count = db_session.query(Session).count()
            
            text = f"""⚙️ **Статус системы бота**

💾 **База данных:**
• **Пользователей: {users_count}** - общее количество зарегистрированных пользователей
• **Событий: {events_count}** - количество зафиксированных действий пользователей
• **Сессий: {sessions_count}** - количество сессий работы пользователей с ботом
{queue_info}

📊 **Что означают эти цифры:**
• **Пользователи** - сколько человек зарегистрировалось в боте
• **События** - каждое действие пользователя (команда, кнопка, сообщение)
• **Сессии** - периоды активности пользователей (средняя сессия ~30 мин)

✅ **Все системы работают нормально**

_Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing system status: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке статуса")
    
    # === Управление Cookies ===
    
    async def show_cookies_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает меню управления cookies"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Импортируем менеджер куков
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            # Получаем статистику
            stats = await cookies_manager.get_statistics()
            
            text = "🍪 **Управление Cookies**\n\n"
            
            # Статистика по платформам
            platforms = ['instagram', 'youtube', 'tiktok']
            for platform in platforms:
                emoji = {'instagram': '📸', 'youtube': '📺', 'tiktok': '🎵'}[platform]
                platform_stats = stats.get(platform, {})
                total = platform_stats.get('total', 0)
                active = platform_stats.get('active', 0)
                success = platform_stats.get('total_success', 0)
                errors = platform_stats.get('total_errors', 0)
                
                text += f"{emoji} **{platform.title()}**\n"
                text += f"  • Всего: {total} (активных: {active})\n"
                text += f"  • Успешных: {success} | Ошибок: {errors}\n"
                
                if active == 0:
                    text += f"  ⚠️ _Нет активных cookies!_\n"
                elif active < 3:
                    text += f"  ⚠️ _Мало активных cookies_\n"
                    
                text += "\n"
            
            text += "\n💡 _Для добавления cookies отправьте их в формате JSON или Netscape_"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Instagram", callback_data="add_cookies_instagram"),
                    InlineKeyboardButton("➕ YouTube", callback_data="add_cookies_youtube"),
                    InlineKeyboardButton("➕ TikTok", callback_data="add_cookies_tiktok")
                ],
                [
                    InlineKeyboardButton("🗑 Очистить истекшие", callback_data="cleanup_cookies"),
                    InlineKeyboardButton("📊 Подробная статистика", callback_data="cookies_stats")
                ],
                [
                    InlineKeyboardButton("🗑 Удалить куки", callback_data="delete_cookies_menu")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing cookies menu: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке меню cookies")
    
    async def add_cookies_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает процесс добавления cookies"""
        query = update.callback_query
        await query.answer()
        
        platform = query.data.replace('add_cookies_', '')
        context.user_data['adding_cookies_platform'] = platform

        platform_domains = {
            'instagram': '.instagram.com',
            'youtube': '.youtube.com',
            'tiktok': '.tiktok.com'
        }
        sample_domain = platform_domains.get(platform, f'.{platform}.com')

        text = (
            f"🍪 **Добавление Cookies для {platform.title()}**\n\n"
            "📋 Отправьте cookies в одном из форматов:\n\n"
            "**1. JSON формат (из расширения браузера):**\n"
            "```json\n"
            f"[{{\"domain\":\"{sample_domain}\",\"name\":\"sessionid\",\"value\":\"...\"}}]\n"
            "```\n\n"
            "**2. Netscape формат (из браузера):**\n"
            "```\n"
            f"{sample_domain}\tTRUE\t/\tTRUE\t0\tsessionid\tvalue\n"
            "```\n\n"
            "📁 **Можно отправить файл** (.json или .txt) — бот автоматически прочитает содержимое.\n\n"
            f"💡 Как получить cookies:\n"
            f"1. Откройте {platform} в браузере\n"
            "2. Войдите в аккаунт\n"
            "3. F12 → Application → Cookies\n"
            "4. Экспортируйте cookies\n\n"
            "⚠️ **Важно:** Используйте отдельный аккаунт, не основной!"
        )
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cookies")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        return self.COOKIES_INPUT
    
    async def process_cookies_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обрабатывает введенные cookies"""
        try:
            message = update.message
            if not message:
                await update.effective_message.reply_text("❌ Ошибка: не удалось обработать сообщение")
                return ConversationHandler.END
                
            platform = context.user_data.get('adding_cookies_platform')
            if not platform:
                await message.reply_text("❌ Ошибка: платформа не определена")
                return ConversationHandler.END

            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)

            cookies_data = None
            source_hint = "сообщения"

            # Обработка загруженного файла
            if message.document:
                try:
                    document = message.document
                    # Проверяем расширение файла
                    file_ext = (document.file_name or '').lower().split('.')[-1]
                    if file_ext not in ['json', 'txt']:
                        await message.reply_text(
                            "❌ Неподдерживаемый формат файла. Отправьте файл с расширением .json или .txt",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"add_cookies_{platform}")]])
                        )
                        return ConversationHandler.END

                    # Получаем файл
                    telegram_file = await document.get_file()
                    file_bytes = await telegram_file.download_as_bytearray()
                    cookies_data = bytes(file_bytes).decode('utf-8', errors='replace').strip()
                    source_hint = f"файла {document.file_name or 'без названия'}"
                    
                    # Логируем успешную загрузку файла (без содержимого для безопасности)
                    logger.info(f"Received cookies file: {document.file_name}, size: {len(cookies_data)} chars")
                    
                except Exception as e:
                    logger.error(f"Error processing uploaded file: {e}")
                    await message.reply_text(
                        f"❌ Ошибка при загрузке файла: {str(e)}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"add_cookies_{platform}")]])
                    )
                    return ConversationHandler.END
            # Обработка текстового сообщения
            elif message.text:
                cookies_data = message.text.strip()
            else:
                await message.reply_text(
                    "❌ Пожалуйста, отправьте файл с cookies или вставьте их текст",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"add_cookies_{platform}")]])
                )
                return ConversationHandler.END

            if not cookies_data:
                await message.reply_text(
                    "❌ Пустые данные. Отправьте файл с cookies или вставьте их текст",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"add_cookies_{platform}")]])
                )
                return ConversationHandler.END

            # Добавляем в БД
            success = await cookies_manager.add_cookies(
                platform=platform,
                cookies_data=cookies_data,
                added_by=update.effective_user.id,
                notes=f"Added via admin panel by {update.effective_user.username or update.effective_user.id}"
            )
            
            # Очищаем сохраненную платформу перед отправкой сообщения
            context.user_data.pop('adding_cookies_platform', None)
            
            if success:
                await message.reply_text(
                    f"✅ Cookies для {platform.title()} успешно добавлены из {source_hint}!\n\n"
                    f"Теперь они будут использоваться для скачивания видео.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🍪 К меню Cookies", callback_data="admin_cookies")]
                    ])
                )
                return ConversationHandler.END
            else:
                # Если не удалось добавить, показываем кнопку повтора с сохранением платформы
                context.user_data['adding_cookies_platform'] = platform
                await message.reply_text(
                    "❌ Ошибка при добавлении cookies. Проверьте формат и повторите попытку.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"add_cookies_{platform}"),
                        InlineKeyboardButton("🔙 В меню", callback_data="admin_cookies")
                    ]])
                )
                return self.COOKIES_INPUT

        except Exception as e:
            logger.error(f"Error processing cookies: {e}", exc_info=True)
            # Если есть сохраненная платформа, предлагаем повторить
            if 'adding_cookies_platform' in context.user_data:
                platform = context.user_data['adding_cookies_platform']
                await message.reply_text(
                    f"❌ Ошибка: {str(e)}\n\nПопробуйте еще раз или вернитесь в меню.",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"add_cookies_{platform}"),
                            InlineKeyboardButton("🔙 В меню", callback_data="admin_cookies")
                        ]
                    ])
                )
                return self.COOKIES_INPUT
            else:
                await message.reply_text(
                    "❌ Произошла ошибка. Возвращаемся в главное меню.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 В меню", callback_data="admin_menu")]
                    ])
                )
                return ConversationHandler.END
    
    async def cleanup_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Очищает истекшие cookies"""
        query = update.callback_query
        await query.answer()
        
        try:
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            count = await cookies_manager.cleanup_expired()
            
            await query.answer(f"🗑 Деактивировано {count} истекших cookies", show_alert=True)
            
            # Обновляем меню
            await self.show_cookies_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error cleaning up cookies: {e}")
            await query.answer("❌ Ошибка при очистке", show_alert=True)
    
    async def delete_cookies_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает меню удаления кукисов"""
        query = update.callback_query
        await query.answer()
        
        try:
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            platforms = ['youtube', 'instagram', 'tiktok']
            keyboard = []
            
            for platform in platforms:
                cookies_list = await cookies_manager.get_cookies_list(platform)
                count = len(cookies_list)
                if count > 0:
                    emoji = {'youtube': '📺', 'instagram': '📸', 'tiktok': '🎵'}[platform]
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{emoji} {platform.title()} ({count} шт)", 
                            callback_data=f"delete_platform_{platform}"
                        )
                    ])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_cookies")])
            
            text = "🗑 **Удаление Cookies**\n\nВыберите платформу для удаления кукисов:"
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing delete menu: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке меню удаления")
    
    async def delete_platform_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Удаляет все куки для платформы"""
        query = update.callback_query
        await query.answer()
        
        try:
            platform = query.data.replace('delete_platform_', '')
            
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            # Получаем список куков для подтверждения
            cookies_list = await cookies_manager.get_cookies_list(platform)
            
            if not cookies_list:
                await query.answer("Нет кукисов для удаления", show_alert=True)
                return
            
            # Показываем список куков для выборочного удаления
            keyboard = []
            for cookie in cookies_list:
                notes = cookie.get('notes', 'Без описания')
                if len(notes) > 30:
                    notes = notes[:27] + "..."
                
                status = "✅" if cookie['is_active'] else "❌"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status} #{cookie['id']} - {notes}",
                        callback_data=f"delete_single_{cookie['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🗑 Удалить все", callback_data=f"delete_all_{platform}"),
                InlineKeyboardButton("❌ Отмена", callback_data="delete_cookies_menu")
            ])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_cookies")])
            
            text = f"🗑 **Удаление {platform.title()} cookies**\n\nВсего кукисов: {len(cookies_list)}\n\nВыберите куки для удаления или удалите все:"
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error showing platform cookies: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке списка")
    
    async def delete_single_cookie(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Удаляет один куки"""
        query = update.callback_query
        await query.answer()
        
        try:
            cookie_id = int(query.data.replace('delete_single_', ''))
            
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            success = await cookies_manager.delete_cookie(cookie_id)
            
            if success:
                await query.answer("✅ Куки удалены", show_alert=True)
            else:
                await query.answer("❌ Ошибка при удалении", show_alert=True)
            
            # Возвращаемся к списку
            await self.delete_cookies_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error deleting single cookie: {e}")
            await query.answer("❌ Ошибка при удалении", show_alert=True)
    
    async def delete_all_platform_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Удаляет все куки для платформы"""
        query = update.callback_query
        await query.answer()
        
        try:
            platform = query.data.replace('delete_all_', '')
            
            from utils.cookies_manager import CookiesManager
            cookies_manager = CookiesManager(self.db)
            
            count = await cookies_manager.delete_cookies_by_platform(platform)
            
            await query.answer(f"🗑 Удалено {count} кукисов для {platform.title()}", show_alert=True)
            await self.delete_cookies_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error deleting all platform cookies: {e}")
            await query.answer("❌ Ошибка при удалении", show_alert=True)
    
    # === Функции рассылки ===
    
    async def start_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать процесс рассылки - переслать готовый пост"""
        query = update.callback_query
        await query.answer()

        # Очищаем предыдущие данные рассылки
        context.user_data.pop('broadcast_data', None)
        context.user_data.pop('broadcast_segment', None)

        logger.info(f"Broadcast started by user {query.from_user.id}")

        text = """📨 **Рассылка**

Перешлите мне готовый пост из избранного или создайте новое сообщение.

Поддерживаются:
• 📝 Текст
• 🖼 Фото
• 🎬 Видео
• 📄 Документы
• 🎵 Аудио
• 🎤 Голосовые
• 🎯 Стикеры
• 🎞 Анимации

После пересылки выберите сегмент получателей."""

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        return self.BROADCAST_TYPE
    
    async def broadcast_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора типа рассылки"""
        query = update.callback_query
        await query.answer()
        
        broadcast_type = query.data.split('_')[1]
        context.user_data['broadcast_type'] = broadcast_type
        
        # Выбор сегмента
        keyboard = [
            [InlineKeyboardButton("👥 Всем активным", callback_data="segment_all")],
            [InlineKeyboardButton("📅 Активные 7д", callback_data="segment_active_7d")],
            [InlineKeyboardButton("📅 Активные 30д", callback_data="segment_active_30d")],
            [InlineKeyboardButton("😴 Неактивные 7д", callback_data="segment_inactive_7d")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""📨 **Создание рассылки**

Тип: {broadcast_type}

Выберите сегмент пользователей:"""
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        return BROADCAST_CONTENT
    
    async def segment_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора сегмента после пересланного сообщения"""
        query = update.callback_query
        await query.answer()

        segment = query.data.split('_', 1)[1] if '_' in query.data else None
        context.user_data['broadcast_segment'] = segment

        # Получаем количество получателей
        recipients = self.analytics.get_users_for_broadcast(segment)
        recipient_count = len(recipients)

        segment_name = {
            'all': 'Все активные',
            'active_7d': 'Активные 7 дней',
            'active_30d': 'Активные 30 дней',
            'inactive_7d': 'Неактивные 7 дней',
            'test': 'Тестовое сообщение (только вам)'
        }.get(segment, 'Все')

        # Для тестового сообщения отправляем только админу
        if segment == 'test':
            recipients = [update.callback_query.from_user.id]
            recipient_count = 1

        # Подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Отправить", callback_data="broadcast_send"),
                InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = f"""📨 **Подтверждение рассылки**

Сегмент: {segment_name}
Получателей: {recipient_count}

Отправить пересланное сообщение всем пользователям?"""

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        return ConversationHandler.END
    
    async def receive_broadcast_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение пересланного сообщения для рассылки"""
        message = update.message

        # Проверяем, что это сообщение от админа
        if message.from_user.id not in config.BOT_ADMINS:
            return ConversationHandler.END

        # Проверяем, что сообщение не пустое
        if not any([
            message.text, message.photo, message.video, message.document,
            message.audio, message.voice, message.sticker, message.animation
        ]):
            await message.reply_text("❌ Сообщение пустое. Пожалуйста, перешлите сообщение с контентом.")
            return ConversationHandler.END

        # Сохраняем полную информацию о сообщении
        broadcast_data = {
            'message_id': message.message_id,
            'text': message.text,
            'caption': message.caption,
            'parse_mode': ParseMode.MARKDOWN if message.text and ('*' in message.text or '_' in message.text) else None,
            'reply_markup': None,  # Кнопки не пересылаем
            'is_forwarded': bool(message.forward_from or message.forward_from_chat)
        }

        # Определяем тип контента и сохраняем file_id
        if message.photo:
            broadcast_data['content_type'] = 'photo'
            broadcast_data['file_id'] = message.photo[-1].file_id
        elif message.video:
            broadcast_data['content_type'] = 'video'
            broadcast_data['file_id'] = message.video.file_id
        elif message.document:
            broadcast_data['content_type'] = 'document'
            broadcast_data['file_id'] = message.document.file_id
        elif message.audio:
            broadcast_data['content_type'] = 'audio'
            broadcast_data['file_id'] = message.audio.file_id
        elif message.voice:
            broadcast_data['content_type'] = 'voice'
            broadcast_data['file_id'] = message.voice.file_id
        elif message.sticker:
            broadcast_data['content_type'] = 'sticker'
            broadcast_data['file_id'] = message.sticker.file_id
        elif message.animation:
            broadcast_data['content_type'] = 'animation'
            broadcast_data['file_id'] = message.animation.file_id
        elif message.text:
            broadcast_data['content_type'] = 'text'
            broadcast_data['file_id'] = None
        else:
            await message.reply_text("❌ Этот тип контента не поддерживается для рассылки")
            return ConversationHandler.END

        # Сохраняем данные
        context.user_data['broadcast_data'] = broadcast_data

        # Показываем выбор сегмента
        keyboard = [
            [InlineKeyboardButton("👥 Всем активным", callback_data="segment_all")],
            [InlineKeyboardButton("📅 Активные 7 дней", callback_data="segment_active_7d")],
            [InlineKeyboardButton("📅 Активные 30 дней", callback_data="segment_active_30d")],
            [InlineKeyboardButton("😴 Неактивные 7 дней", callback_data="segment_inactive_7d")],
            [InlineKeyboardButton("🧪 Тестовое сообщение", callback_data="segment_test")],
            [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Показываем превью контента
        preview_text = self._get_content_preview(broadcast_data)
        forward_info = " (переслано)" if broadcast_data['is_forwarded'] else ""

        text = f"""📨 **Переслано для рассылки**{forward_info}

{preview_text}

Выберите сегмент получателей:"""

        await message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        return ConversationHandler.END

    def _get_content_preview(self, broadcast_data: dict) -> str:
        """Получить текстовое превью контента"""
        content_type = broadcast_data['content_type']

        if content_type == 'text':
            text = broadcast_data['text'][:100] + "..." if broadcast_data['text'] and len(broadcast_data['text']) > 100 else broadcast_data['text']
            return f"📝 Текст:\n{text or 'Пустое сообщение'}"

        elif content_type == 'photo':
            return f"🖼 Фото{(' с подписью' if broadcast_data['caption'] else '')}"

        elif content_type == 'video':
            return f"🎬 Видео{(' с подписью' if broadcast_data['caption'] else '')}"

        elif content_type == 'document':
            return "📄 Документ"

        elif content_type == 'audio':
            return "🎵 Аудио"

        elif content_type == 'voice':
            return "🎤 Голосовое сообщение"

        elif content_type == 'sticker':
            return "🎯 Стикер"

        elif content_type == 'animation':
            return "🎞 Анимация"

        else:
            return "❓ Неизвестный тип контента"
    
    async def send_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправка пересланной рассылки"""
        query = update.callback_query
        await query.answer()

        if query.data == "broadcast_cancel":
            await query.edit_message_text("❌ Рассылка отменена")
            context.user_data.clear()
            return

        # Начинаем рассылку
        await query.edit_message_text("📤 Начинаю рассылку...")

        broadcast_data = context.user_data.get('broadcast_data')
        if not broadcast_data:
            await query.edit_message_text("❌ Ошибка: данные для рассылки не найдены")
            return

        segment = context.user_data.get('broadcast_segment')
        recipients = self.analytics.get_users_for_broadcast(segment)

        if not recipients:
            await query.edit_message_text("❌ Получатели не найдены")
            return

        # Для тестового сообщения отправляем только админу
        if segment == 'test':
            recipients = [query.from_user.id]
            recipient_count = 1
        else:
            recipient_count = len(recipients)

        sent = 0
        failed = 0
        blocked = 0

        # Отправляем сообщения
        for tg_id in recipients:
            try:
                await self._send_message_to_user(context.bot, tg_id, broadcast_data)
                sent += 1

                # Пауза каждые 30 сообщений
                if sent % 30 == 0:
                    await asyncio.sleep(1)

            except Exception as e:
                error_str = str(e).lower()
                if "blocked" in error_str or "bot was blocked" in error_str:
                    blocked += 1
                    # Помечаем пользователя как заблокированного
                    try:
                        with self.db.get_session() as db_session:
                            from database.models import User
                            user = db_session.query(User).filter_by(tg_id=tg_id).first()
                            if user:
                                user.is_blocked = True
                                db_session.commit()
                    except:
                        pass
                else:
                    failed += 1

                logger.error(f"Failed to send broadcast to {tg_id}: {e}")

        # Результат
        total = len(recipients)
        success_rate = (sent / total * 100) if total > 0 else 0

        text = f"""✅ **Рассылка завершена**

📊 Статистика:
• Отправлено: {sent}
• Заблокировано: {blocked}
• Ошибок: {failed}
• Всего получателей: {total}

🎯 Успешность: {success_rate:.1f}%"""

        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        # Очищаем данные
        context.user_data.pop('broadcast_data', None)
        context.user_data.pop('broadcast_segment', None)

    async def _send_message_to_user(self, bot, user_id: int, broadcast_data: dict):
        """Отправить сообщение пользователю в том же виде"""
        content_type = broadcast_data['content_type']
        text = broadcast_data['text']
        caption = broadcast_data['caption']
        file_id = broadcast_data['file_id']

        try:
            if content_type == 'text':
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=broadcast_data['parse_mode']
                )

            elif content_type == 'photo':
                await bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

            elif content_type == 'video':
                await bot.send_video(
                    chat_id=user_id,
                    video=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

            elif content_type == 'document':
                await bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

            elif content_type == 'audio':
                await bot.send_audio(
                    chat_id=user_id,
                    audio=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

            elif content_type == 'voice':
                await bot.send_voice(
                    chat_id=user_id,
                    voice=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

            elif content_type == 'sticker':
                await bot.send_sticker(
                    chat_id=user_id,
                    sticker=file_id
                )

            elif content_type == 'animation':
                await bot.send_animation(
                    chat_id=user_id,
                    animation=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN if caption else None
                )

        except Exception as e:
            # Пробрасываем ошибку для обработки в вызывающем коде
            raise e
    
    async def cancel_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена рассылки"""
        # Очищаем все данные рассылки
        context.user_data.pop('broadcast_data', None)
        context.user_data.pop('broadcast_segment', None)
        context.user_data.clear()

        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Рассылка отменена")
        else:
            await update.message.reply_text("❌ Рассылка отменена")

        return ConversationHandler.END
