"""
Обработчики для Gmail-алиасов
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.localization import get_text
from services.gmail_aliases import generate_gmail_aliases, validate_gmail_input

logger = logging.getLogger(__name__)


class GmailAliasHandler:
    """Обработчик Gmail-алиасов"""
    
    MAX_DAILY_QUOTA = 10
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать главное меню Gmail-алиасов"""
        try:
            # Определяем источник вызова
            if update.callback_query:
                query = update.callback_query
                await query.answer()
                chat_id = query.message.chat.id
                message_id = query.message.message_id
                edit_message = True
            else:
                chat_id = update.effective_chat.id
                message_id = None
                edit_message = False
            
            user_id = update.effective_user.id
            
            # Получаем оставшуюся квоту
            remaining_quota = 0
            if 'database' in context.bot_data:
                db = context.bot_data['database']
                remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
            
            # Создаем текст сообщения
            text = get_text(context, 'gmail_aliases_menu').format(
                remaining_quota=remaining_quota,
                max_quota=self.MAX_DAILY_QUOTA
            )
            
            # Создаем клавиатуру
            keyboard = []
            
            if remaining_quota > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        get_text(context, 'generate_aliases'), 
                        callback_data="gmail_generate"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(
                    get_text(context, 'back'), 
                    callback_data="main_menu"
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if edit_message and message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error showing Gmail aliases menu: {e}")
            await self._send_error_message(update, context)
    
    async def request_email_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Запрашивает ввод Gmail адреса"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            
            # Проверяем квоту
            remaining_quota = 0
            if 'database' in context.bot_data:
                db = context.bot_data['database']
                remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
            
            if remaining_quota <= 0:
                text = get_text(context, 'gmail_quota_exceeded')
                keyboard = [[
                    InlineKeyboardButton(
                        get_text(context, 'back_to_gmail'), 
                        callback_data="gmail_menu"
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            text = get_text(context, 'gmail_request_email')
            
            keyboard = [[
                InlineKeyboardButton(
                    get_text(context, 'back_to_gmail'), 
                    callback_data="gmail_menu"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Устанавливаем флаг ожидания email
            context.user_data['awaiting_gmail_input'] = True
            
        except Exception as e:
            logger.error(f"Error requesting email input: {e}")
            await self._send_error_message(update, context)
    
    async def process_email_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает введенный пользователем email"""
        try:
            # Проверяем, ожидаем ли мы email
            if not context.user_data.get('awaiting_gmail_input'):
                return
            
            # Убираем флаг ожидания
            context.user_data['awaiting_gmail_input'] = False
            
            # Получаем введенный email
            email = update.message.text.strip()
            
            # Валидируем email
            is_valid, error_message, is_gmail = validate_gmail_input(email)
            
            if not is_valid:
                await update.message.reply_text(
                    get_text(context, 'gmail_invalid_email').format(error=error_message),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Если не Gmail домен - предупреждение
            if not is_gmail:
                text = get_text(context, 'gmail_non_gmail_warning')
                
                keyboard = [
                    [
                        InlineKeyboardButton(
                            get_text(context, 'continue_anyway'), 
                            callback_data=f"gmail_continue_{email}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            get_text(context, 'back_to_gmail'), 
                            callback_data="gmail_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Gmail домен - переходим к выбору количества
            await self._show_count_selection(update, context, email)
            
        except Exception as e:
            logger.error(f"Error processing email input: {e}")
            await update.message.reply_text(
                get_text(context, 'error_processing'),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def process_count_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает введенное пользователем количество адресов"""
        try:
            # Проверяем, ожидаем ли мы ввод количества
            if not context.user_data.get('awaiting_gmail_count_input'):
                return
            
            # Убираем флаг ожидания
            context.user_data['awaiting_gmail_count_input'] = False
            
            # Получаем email из контекста
            email = context.user_data.get('gmail_email')
            if not email:
                await update.message.reply_text(
                    get_text(context, 'gmail_no_email'),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Получаем введенное количество
            count_text = update.message.text.strip()
            
            # Проверяем, что введено число
            try:
                count = int(count_text)
            except ValueError:
                # Получаем оставшуюся квоту для отображения в ошибке
                user_id = update.effective_user.id
                remaining_quota = self.MAX_DAILY_QUOTA
                if 'database' in context.bot_data:
                    db = context.bot_data['database']
                    remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
                
                await update.message.reply_text(
                    get_text(context, 'gmail_invalid_count').format(max_count=remaining_quota),
                    parse_mode=ParseMode.MARKDOWN
                )
                # Снова устанавливаем флаг ожидания ввода
                context.user_data['awaiting_gmail_count_input'] = True
                return
            
            user_id = update.effective_user.id
            
            # Получаем оставшуюся квоту
            remaining_quota = self.MAX_DAILY_QUOTA
            if 'database' in context.bot_data:
                db = context.bot_data['database']
                remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
            
            # Проверяем диапазон
            if count < 1 or count > remaining_quota:
                await update.message.reply_text(
                    get_text(context, 'gmail_invalid_count').format(max_count=remaining_quota),
                    parse_mode=ParseMode.MARKDOWN
                )
                # Снова устанавливаем флаг ожидания ввода
                context.user_data['awaiting_gmail_count_input'] = True
                return
            
            # Генерируем алиасы
            try:
                aliases = generate_gmail_aliases(email, count)
            except ValueError as e:
                await update.message.reply_text(
                    get_text(context, 'gmail_generation_error').format(error=str(e)),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Обновляем квоту в БД
            if 'database' in context.bot_data:
                db = context.bot_data['database']
                await db.increment_gmail_usage(user_id, count)
                # Получаем обновленную квоту
                remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
            
            # Форматируем алиасы в моноширинный блок
            aliases_text = '\n'.join(aliases)
            
            # Создаем сообщение с результатами
            result_text = get_text(context, 'gmail_aliases_result').format(
                count=count,
                remaining_quota=remaining_quota,
                aliases=aliases_text
            )
            
            # Создаем клавиатуру
            keyboard = []
            
            if remaining_quota > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        get_text(context, 'generate_more'), 
                        callback_data="gmail_generate"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(
                    get_text(context, 'back_to_gmail'), 
                    callback_data="gmail_menu"
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text=result_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error processing count input: {e}")
            await update.message.reply_text(
                get_text(context, 'error_processing'),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def continue_with_non_gmail(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Продолжает с не-Gmail доменом после подтверждения"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем email из callback_data
            email = query.data.replace("gmail_continue_", "")
            
            # Переходим к выбору количества
            await self._show_count_selection(update, context, email, edit_message=True)
            
        except Exception as e:
            logger.error(f"Error continuing with non-Gmail: {e}")
            await self._send_error_message(update, context)
    
    async def _show_count_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  email: str, edit_message: bool = False) -> None:
        """Показывает выбор количества алиасов"""
        try:
            user_id = update.effective_user.id
            
            # Получаем оставшуюся квоту
            remaining_quota = self.MAX_DAILY_QUOTA
            if 'database' in context.bot_data:
                db = context.bot_data['database']
                remaining_quota = await db.get_gmail_remaining_quota(user_id, self.MAX_DAILY_QUOTA)
            
            if remaining_quota <= 0:
                text = get_text(context, 'gmail_quota_exceeded')
                keyboard = [[
                    InlineKeyboardButton(
                        get_text(context, 'back_to_gmail'), 
                        callback_data="gmail_menu"
                    )
                ]]
            else:
                # Сохраняем email в контексте
                context.user_data['gmail_email'] = email
                
                text = get_text(context, 'gmail_choose_count').format(
                    remaining_quota=remaining_quota
                )
                
                # Устанавливаем флаг ожидания ввода количества
                context.user_data['awaiting_gmail_count_input'] = True
                
                # Только кнопка "Назад"
                keyboard = [[
                    InlineKeyboardButton(
                        get_text(context, 'back_to_gmail'), 
                        callback_data="gmail_menu"
                    )
                ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if edit_message:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await update.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error showing count selection: {e}")
            await self._send_error_message(update, context)
    
    
    async def _send_error_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет сообщение об ошибке"""
        try:
            error_text = get_text(context, 'error_processing')
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")


# Глобальный экземпляр обработчика
gmail_handler = GmailAliasHandler()


# Экспортируемые функции для использования в main.py
async def gmail_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для меню Gmail-алиасов"""
    await gmail_handler.show_main_menu(update, context)


async def gmail_generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для запуска генерации"""
    await gmail_handler.request_email_input(update, context)



async def gmail_continue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для продолжения с не-Gmail доменом"""
    await gmail_handler.continue_with_non_gmail(update, context)


async def gmail_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений для Gmail-алиасов"""
    # Проверяем, ожидаем ли мы ввод email или количества
    if context.user_data.get('awaiting_gmail_input'):
        await gmail_handler.process_email_input(update, context)
    elif context.user_data.get('awaiting_gmail_count_input'):
        await gmail_handler.process_count_input(update, context)
