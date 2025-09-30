"""
Обработчик уникализации медиафайлов
"""

import os
import logging
import asyncio
import zipfile
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from utils import create_multiple_unique_images, create_multiple_unique_videos
from utils.localization import get_text
import config

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_FILE = 0
WAITING_FOR_COPIES = 1


async def start_uniqizer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса уникализации"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сначала просим загрузить файл
    await query.message.reply_text(
        text=get_text(context, 'upload_file'),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_FILE


async def copies_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода количества копий"""
    message = update.message
    text = message.text.strip()
    
    # Проверяем, что это число
    try:
        copies = int(text)
        
        # Проверяем диапазон
        if copies < 1 or copies > 25:
            keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.reply_text(
                text=get_text(context, 'invalid_copies_number'),
                reply_markup=reply_markup
            )
            return WAITING_FOR_COPIES
        
        # Сохраняем количество копий
        context.user_data['copies_count'] = copies
        
        # Получаем сохраненные данные о файле
        file_obj = context.user_data.get('file_obj')
        file_name = context.user_data.get('file_name')
        is_compressed = context.user_data.get('is_compressed', False)
        
        if not file_obj or not file_name:
            await message.reply_text("Ошибка: не найден файл для обработки")
            return ConversationHandler.END
        
        # Подтверждаем выбор и начинаем обработку
        processing_msg = await message.reply_text(
            text=f"🔄 Создаем {copies} уникальных копий..."
        )
        
        # Начинаем обработку файла
        return await process_media_file(update, context, file_obj, file_name, processing_msg, is_compressed)
        
    except ValueError:
        # Если не число
        keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            text=get_text(context, 'invalid_copies_number'),
            reply_markup=reply_markup
        )
        return WAITING_FOR_COPIES


async def wrong_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик сжатого медиа (видео/фото не как файл)"""
    message = update.message
    user = update.effective_user
    
    # Определяем тип медиа и получаем файл объект
    if message.video:
        media_type = "видео"
        file_obj = message.video
        file_name = f"video_{user.id}_{message.message_id}.mp4"
    elif message.photo:
        media_type = "фото"
        file_obj = message.photo[-1]
        file_name = f"photo_{user.id}_{message.message_id}.jpg"
    else:
        await message.reply_text(text=get_text(context, 'error_no_file'))
        return WAITING_FOR_FILE
    
    # Проверяем размер файла против наших лимитов
    if file_obj.file_size > config.MAX_FILE_SIZE:
        max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
        await message.reply_text(text=get_text(context, 'error_file_too_large', max_size=max_size_mb))
        return WAITING_FOR_FILE
    
    # Сохраняем информацию о файле
    context.user_data['file_obj'] = file_obj
    context.user_data['file_name'] = file_name
    context.user_data['is_compressed'] = True
    
    # Спрашиваем количество копий
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text=get_text(context, 'choose_copies'),
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_COPIES


async def process_media_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_obj, file_name: str, processing_msg=None, is_compressed: bool = False) -> int:
    """Универсальная функция обработки медиафайлов"""
    message = update.message
    user = update.effective_user
    
    # Получаем количество копий
    copies_count = context.user_data.get('copies_count', 1)
    
    # Отправляем сообщение о начале обработки (если еще не отправлено)
    if not processing_msg:
        processing_msg = await message.reply_text(text=get_text(context, 'processing', count=copies_count))
    
    try:
        # Создаем временную директорию для работы
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Автоматически обрабатываем файлы любого размера
            from utils.smart_compressor import compress_for_telegram, compress_video_ffmpeg, compress_image_pillow
            
            input_path = None
            file_size_mb = file_obj.file_size / (1024 * 1024)
            
            # Progress callback - минимальные уведомления
            async def progress_callback(stage, info):
                # Никаких уведомлений о сжатии - просто обрабатываем
                pass
            
            # Скачиваем файл (с автоматическим сжатием если нужно)
            input_path, error = await compress_for_telegram(
                bot=context.bot,
                file_id=file_obj.file_id,
                original_filename=file_name,
                progress_callback=progress_callback
            )
            
            # Если не удалось скачать - ошибка
            if not input_path:
                await processing_msg.edit_text("❌ Ошибка обработки файла")
                return WAITING_FOR_FILE
            
            # Никаких дополнительных сообщений - сжатие уже произошло автоматически
            
            # Определяем тип файла
            file_extension = input_path.suffix.lower()
            is_video = file_extension in config.SUPPORTED_VIDEO_FORMATS or file_name.endswith('.mp4')
            is_image = file_extension in config.SUPPORTED_IMAGE_FORMATS or file_name.endswith('.jpg')
            
            if not is_video and not is_image:
                await processing_msg.edit_text(text=get_text(context, 'error_unsupported_format'))
                return WAITING_FOR_FILE
            
            # Создаем директорию для результатов
            output_dir = temp_path / 'output'
            output_dir.mkdir(exist_ok=True)
            
            logger.info(f"User {user.id} uploaded {file_name} ({file_obj.file_size} bytes, compressed: {is_compressed})")
            
            # Обрабатываем файл
            if is_video:
                # Callback для отправки прогресса
                async def progress_callback(current, total):
                    await processing_msg.edit_text(
                        text=get_text(context, 'processing_video', current=current, total=total)
                    )
                
                results = await create_multiple_unique_videos(
                    str(input_path),
                    str(output_dir),
                    copies_count,
                    config.VIDEO_UNIQUENESS_PARAMS,
                    progress_callback
                )
            else:
                # Обновляем сообщение для изображений
                await processing_msg.edit_text(
                    text=get_text(context, 'processing_image', current=1, total=copies_count)
                )
                
                results = create_multiple_unique_images(
                    str(input_path),
                    str(output_dir),
                    copies_count,
                    config.IMAGE_UNIQUENESS_PARAMS
                )
            
            # Создаем ZIP архив с результатами
            await processing_msg.edit_text(text=get_text(context, 'creating_archive'))
            
            zip_path = temp_path / f"unique_{user.id}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for result_path in results:
                    arcname = os.path.basename(result_path)
                    zipf.write(result_path, arcname)
            
            # Отправляем архив пользователю
            await processing_msg.delete()
            
            # Простое сообщение об успехе без лишних деталей
            caption_text = get_text(context, 'success', count=len(results))
            
            with open(zip_path, 'rb') as zip_file:
                await message.reply_document(
                    document=zip_file,
                    filename=f"unique_files_{copies_count}.zip",
                    caption=caption_text
                )
            
            logger.info(f"Successfully processed {file_name} for user {user.id}, created {len(results)} copies")
            
    except Exception as e:
        logger.error(f"Error processing media file: {e}")
        
        # Общая ошибка обработки
        await processing_msg.edit_text(
            text=f"❌ **Ошибка обработки файла**\n\n"
                 f"🔧 Попробуйте:\n"
                 f"• Проверить формат файла\n"
                 f"• Уменьшить размер файла\n"
                 f"• Отправить файл еще раз\n\n"
                 f"💭 Если проблема повторяется, обратитесь к администратору"
        )
        return WAITING_FOR_FILE
    
    # Показываем предложение повторить или вернуться в меню
    keyboard = [[
        InlineKeyboardButton(get_text(context, 'uniqueness_tool'), callback_data='uniqueness_tool'),
        InlineKeyboardButton(get_text(context, 'main_menu'), callback_data='main_menu')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text=get_text(context, 'uniqueness_more_or_menu'),
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик загруженного документа"""
    message = update.message
    
    # Проверяем, что это документ
    if not message.document:
        await message.reply_text(text=get_text(context, 'error_no_file'))
        return WAITING_FOR_FILE
    
    document = message.document
    
    # Проверяем размер файла против наших лимитов
    if document.file_size > config.MAX_FILE_SIZE:
        max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
        await message.reply_text(text=get_text(context, 'error_file_too_large', max_size=max_size_mb))
        return WAITING_FOR_FILE
    
    
    # Проверяем формат файла
    file_extension = Path(document.file_name).suffix.lower()
    is_video = file_extension in config.SUPPORTED_VIDEO_FORMATS
    is_image = file_extension in config.SUPPORTED_IMAGE_FORMATS
    
    if not is_video and not is_image:
        await message.reply_text(text=get_text(context, 'error_unsupported_format'))
        return WAITING_FOR_FILE
    
    # Сохраняем информацию о файле
    context.user_data['file_obj'] = document
    context.user_data['file_name'] = document.file_name
    context.user_data['is_compressed'] = False
    
    # Теперь спрашиваем количество копий
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text=get_text(context, 'choose_copies'),
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_COPIES


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отмены операции"""
    # Очищаем user_data
    context.user_data.clear()
    
    # Возвращаемся в главное меню
    from .subscription import show_main_menu
    await show_main_menu(update, context)
    
    return ConversationHandler.END


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик возврата в главное меню"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем user_data кроме языка
    lang = context.user_data.get('language')
    context.user_data.clear()
    if lang:
        context.user_data['language'] = lang
    
    # Показываем главное меню
    from .subscription import show_main_menu
    await show_main_menu(update, context)
    
    return ConversationHandler.END
