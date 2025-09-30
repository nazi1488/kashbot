"""
Random Face Handlers

Обработчики команд и callback-запросов для генерации случайных лиц.

UX: только sendPhoto, без скачивания или отправки документов.
Каждое сгенерированное лицо отправляется как фото с подписью.
"""

import logging
from typing import TYPE_CHECKING

from telegram import Update, InputFile
from telegram.ext import ContextTypes, CallbackQueryHandler

from features.random_face.service import RandomFaceService
from features.random_face.keyboard import RandomFaceKeyboard
from utils.localization import get_text

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RandomFaceHandlers:
    """Обработчики для генерации случайных лиц"""
    
    def __init__(self, redis: 'Redis'):
        self.service = RandomFaceService(redis)
        self.keyboard = RandomFaceKeyboard()
    
    async def show_random_face_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Показать главное меню раздела Random Face
        
        Отображает информацию о сервисе и кнопки для генерации.
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        remaining_quota = await self.service.get_remaining_quota(user_id)
        
        # Формируем текст меню
        menu_text = (
            "👤 **Random Face Generator**\n\n"
            "🧪 Генерируем синтетические лица людей, которых не существует.\n"
            "🎨 Каждое лицо уникально и создано нейросетью.\n\n"
            f"📊 **Осталось сегодня:** {remaining_quota} из {context.bot_data.get('FACE_QUOTA_PER_DAY', 10)}\n\n"
            "💡 Нажмите «Сгенерировать» для получения нового лица."
        )
        
        await query.edit_message_text(
            text=menu_text,
            reply_markup=self.keyboard.main_menu(),
            parse_mode='Markdown'
        )
    
    async def generate_random_face(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Сгенерировать и отправить случайное лицо
        
        Обрабатывает как первичную генерацию, так и повторные запросы.
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Показываем индикатор загрузки
        loading_text = "⏳ Генерируем новое лицо...\n\n🎨 Это займет несколько секунд"
        
        # Проверяем, можно ли отредактировать сообщение как текст
        try:
            # Если предыдущее сообщение содержит текст, редактируем его
            if query.message.text:
                await query.edit_message_text(text=loading_text)
            else:
                # Если это фото или другой тип, отправляем новое сообщение
                loading_message = await query.message.reply_text(text=loading_text)
                # Сохраняем ссылку на сообщение загрузки для последующего удаления
                context.user_data['loading_message'] = loading_message
        except Exception:
            # Fallback: отправляем новое сообщение
            loading_message = await query.message.reply_text(text=loading_text)
            context.user_data['loading_message'] = loading_message
        
        try:
            # Получаем изображение от сервиса
            image_data, error_message = await self.service.fetch_face_image(user_id)
            
            if error_message:
                # Показываем ошибку пользователю
                error_text = f"❌ {error_message}"
                try:
                    if query.message.text:
                        await query.edit_message_text(
                            text=error_text,
                            reply_markup=self.keyboard.main_menu()
                        )
                    else:
                        # Удаляем сообщение загрузки если оно было создано
                        if 'loading_message' in context.user_data:
                            try:
                                await context.user_data['loading_message'].delete()
                                del context.user_data['loading_message']
                            except:
                                pass
                        # Отправляем новое сообщение с ошибкой
                        await query.message.reply_text(
                            text=error_text,
                            reply_markup=self.keyboard.main_menu()
                        )
                except:
                    # Fallback: просто отправляем новое сообщение
                    await query.message.reply_text(
                        text=error_text,
                        reply_markup=self.keyboard.main_menu()
                    )
                return
            
            if image_data is None:
                # Общая ошибка
                error_text = "❌ Не удалось сгенерировать лицо. Попробуйте ещё раз."
                try:
                    if query.message.text:
                        await query.edit_message_text(
                            text=error_text,
                            reply_markup=self.keyboard.main_menu()
                        )
                    else:
                        # Удаляем сообщение загрузки если оно было создано
                        if 'loading_message' in context.user_data:
                            try:
                                await context.user_data['loading_message'].delete()
                                del context.user_data['loading_message']
                            except:
                                pass
                        await query.message.reply_text(
                            text=error_text,
                            reply_markup=self.keyboard.main_menu()
                        )
                except:
                    await query.message.reply_text(
                        text=error_text,
                        reply_markup=self.keyboard.main_menu()
                    )
                return
            
            # Подготавливаем файл для отправки
            image_file = InputFile(
                obj=image_data,
                filename="random_face.jpg"
            )
            
            # Формируем подпись к фото
            caption = (
                "🧪 Синтетическое лицо (не реальный человек).\n"
                "Сгенерировано нейросетью thispersondoesnotexist.com\n\n"
                "🔁 Обнови ещё раз, если хочешь другую фотографию."
            )
            
            # Отправляем фото
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=image_file,
                caption=caption,
                reply_markup=self.keyboard.after_generation()
            )
            
            # Удаляем сообщение с загрузкой
            try:
                if query.message.text:
                    # Если это текстовое сообщение, можем его удалить
                    await query.delete_message()
                elif 'loading_message' in context.user_data:
                    # Удаляем отдельно созданное сообщение загрузки
                    await context.user_data['loading_message'].delete()
                    del context.user_data['loading_message']
            except Exception as e:
                # Игнорируем ошибки удаления - не критично
                logger.warning(f"Could not delete loading message: {e}")
            
            logger.info(f"Successfully sent random face to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error generating face for user {user_id}: {type(e).__name__}: {e}")
            
            error_text = "❌ Произошла ошибка при генерации. Попробуйте позже."
            try:
                if query.message.text:
                    await query.edit_message_text(
                        text=error_text,
                        reply_markup=self.keyboard.main_menu()
                    )
                else:
                    # Очищаем сообщение загрузки если есть
                    if 'loading_message' in context.user_data:
                        try:
                            await context.user_data['loading_message'].delete()
                            del context.user_data['loading_message']
                        except:
                            pass
                    await query.message.reply_text(
                        text=error_text,
                        reply_markup=self.keyboard.main_menu()
                    )
            except:
                # Последний fallback
                try:
                    await query.message.reply_text(
                        text=error_text,
                        reply_markup=self.keyboard.main_menu()
                    )
                except:
                    pass
    
    async def handle_more_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработать запрос на повторную генерацию
        
        Аналогично основной генерации, но с учетом контекста повтора.
        """
        # Повторная генерация использует ту же логику
        await self.generate_random_face(update, context)


# Глобальная переменная для handlers
_handlers_instance = None

def get_handlers_instance(redis: 'Redis') -> RandomFaceHandlers:
    """Получить экземпляр handlers (singleton)"""
    global _handlers_instance
    if _handlers_instance is None:
        _handlers_instance = RandomFaceHandlers(redis)
    return _handlers_instance


async def show_random_face_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для показа меню Random Face"""
    if 'random_face_handlers' in context.bot_data:
        await context.bot_data['random_face_handlers'].show_random_face_menu(update, context)


async def generate_random_face_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для генерации лица"""
    if 'random_face_handlers' in context.bot_data:
        await context.bot_data['random_face_handlers'].generate_random_face(update, context)


async def handle_more_generation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для повторной генерации"""
    if 'random_face_handlers' in context.bot_data:
        await context.bot_data['random_face_handlers'].handle_more_generation(update, context)


def register_random_face_handlers(application, redis: 'Redis') -> None:
    """
    Регистрация обработчиков Random Face в приложении
    
    Args:
        application: Экземпляр приложения Telegram бота
        redis: Подключение к Redis
    """
    handlers = get_handlers_instance(redis)
    
    # Сохраняем handlers в bot_data для доступа из callbacks
    application.bot_data['random_face_handlers'] = handlers
    
    # Регистрируем обработчики callback-запросов
    application.add_handler(
        CallbackQueryHandler(
            show_random_face_menu_callback,
            pattern="^random_face_menu$"
        )
    )
    
    application.add_handler(
        CallbackQueryHandler(
            generate_random_face_callback,
            pattern="^random_face_generate$"
        )
    )
    
    application.add_handler(
        CallbackQueryHandler(
            handle_more_generation_callback,
            pattern="^random_face_more$"
        )
    )
    
    logger.info("Random Face handlers registered successfully")
