"""
Обработчик для умного сжатия медиафайлов для Facebook
"""

import os
import logging
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from utils.localization import get_text
from utils.compress_utils import (
    compress_image_for_facebook,
    compress_video_for_facebook,
    is_video_file,
    is_image_file
)
from utils.queue_manager import compression_queue
import config

logger = logging.getLogger(__name__)

# Состояние для ConversationHandler
WAITING_FOR_COMPRESS_FILE = 0


async def smart_compress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Умное сжатие'"""
    query = update.callback_query
    await query.answer()
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', 'smart_compress')
    
    # Отправляем объяснение
    await query.message.reply_text(
        text=get_text(context, 'smart_compress_explanation'),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Показываем кнопку отмены
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Просим загрузить файл
    await query.message.reply_text(
        text=get_text(context, 'upload_file_compress'),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_COMPRESS_FILE


async def wrong_media_handler_compress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик сжатого медиа (видео/фото не как файл) для компрессора"""
    message = update.message
    user = update.effective_user
    
    # Определяем тип медиа и получаем файл объект
    if message.video:
        media_type = "видео"
        file_obj = message.video
        # Генерируем имя файла для видео
        file_name = f"video_{user.id}_{message.message_id}.mp4"
    elif message.photo:
        media_type = "фото"
        # Берем самое большое фото
        file_obj = message.photo[-1]
        file_name = f"photo_{user.id}_{message.message_id}.jpg"
    else:
        await message.reply_text(text=get_text(context, 'error_no_file'))
        return WAITING_FOR_COMPRESS_FILE
    
    # Проверяем размер файла
    if file_obj.file_size > config.MAX_FILE_SIZE:
        max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
        await message.reply_text(text=get_text(context, 'error_file_too_large', max_size=max_size_mb))
        return WAITING_FOR_COMPRESS_FILE
    
    # Показываем предупреждение о качестве, но принимаем файл
    quality_warning = await message.reply_text(
        text=f"⚠️ **{media_type.capitalize()} принято к сжатию!**\n\n"
             f"💡 **Совет на будущее:**\n"
             f"Для лучшего качества отправляйте {media_type} как файл:\n"
             f"• 📎 Скрепка → \"Файл\" → выберите {media_type}\n"
             f"• На телефоне: выберите опцию \"Без сжатия\"\n\n"
             f"🔄 Сейчас сжимаем ваш {media_type}...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Создаем временный документ объект для совместимости с process_compression_task
    class TempDocument:
        def __init__(self, file_obj, file_name):
            self.file_id = file_obj.file_id
            self.file_name = file_name
            self.file_size = file_obj.file_size
            
        async def get_file(self):
            return await context.bot.get_file(self.file_id)
    
    temp_document = TempDocument(file_obj, file_name)
    
    # Добавляем задачу в очередь (как в обычном обработчике)
    queue_result = await compression_queue.add_task(
        user_id=user.id,
        task_func=process_compression_task,
        message=message,
        document=temp_document,
        file_name=file_name,
        context=context
    )
    
    if not queue_result['success']:
        # Обработка ошибок очереди
        if queue_result['error'] == 'too_many_tasks':
            await message.reply_text(
                text=get_text(context, 'too_many_tasks')
            )
        elif queue_result['error'] == 'queue_full':
            await message.reply_text(
                text=get_text(context, 'queue_full', queue_size=queue_result.get('queue_size', 10))
            )
        else:
            await message.reply_text(
                text=get_text(context, 'error_processing')
            )
    else:
        # Задача успешно добавлена в очередь
        await message.reply_text(
            text=get_text(
                context,
                'queue_position',
                position=queue_result['position'],
                current=queue_result['current_tasks'],
                max=queue_result['max_concurrent']
            )
        )
        
        logger.info(f"User {user.id} added compressed {media_type} to compression queue, position: {queue_result['position']}")
    
    return ConversationHandler.END


async def process_compression_task(
    message,
    document,
    file_name: str,
    context: ContextTypes.DEFAULT_TYPE
):
    """Функция для обработки сжатия (будет вызываться из очереди)"""
    processing_msg = None
    
    try:
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as temp_dir:
            # Скачиваем файл
            input_path = os.path.join(temp_dir, file_name)
            file = await document.get_file()
            await file.download_to_drive(input_path)
            
            logger.info(f"Processing compression: {file_name}")
            
            # Создаем директорию для результата
            output_dir = os.path.join(temp_dir, 'compressed')
            os.makedirs(output_dir, exist_ok=True)
            
            # Обновляем сообщение о процессе
            processing_msg = await message.reply_text(
                text=get_text(context, 'compressing')
            )
            
            # Сжимаем файл
            if is_image_file(file_name):
                # Сжимаем изображение
                output_path, stats = compress_image_for_facebook(
                    input_path,
                    output_dir,
                    target_format='webp'
                )
            else:
                # Сжимаем видео
                output_path, stats = await compress_video_for_facebook(
                    input_path,
                    output_dir
                )
            
            # Удаляем сообщение о процессе
            if processing_msg:
                await processing_msg.delete()
            
            # Отправляем сжатый файл
            with open(output_path, 'rb') as compressed_file:
                await message.reply_document(
                    document=compressed_file,
                    filename=os.path.basename(output_path),
                    caption=get_text(
                        context,
                        'compression_report',
                        original_size=stats['original_size'],
                        new_size=stats['new_size'],
                        percent=stats['percent'],
                        saved=stats['saved']
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            
            logger.info(f"Successfully compressed {file_name}: "
                       f"{stats['original_size']}MB -> {stats['new_size']}MB ({stats['percent']}%)")
            
            # Показываем предложение повторить после успешного сжатия
            keyboard = [[
                InlineKeyboardButton(get_text(context, 'smart_compress'), callback_data='smart_compress'),
                InlineKeyboardButton(get_text(context, 'main_menu'), callback_data='main_menu')
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.reply_text(
                text=get_text(context, 'compress_more_or_menu'),
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Error in compression task: {e}")
        if processing_msg:
            await processing_msg.edit_text(
                text=get_text(context, 'error_processing')
            )
        raise


async def compress_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик загруженного файла для сжатия"""
    message = update.message
    user = update.effective_user
    
    # Проверяем, что это документ
    if not message.document:
        await message.reply_text(
            text=get_text(context, 'error_no_file')
        )
        return WAITING_FOR_COMPRESS_FILE
    
    document = message.document
    file_name = document.file_name
    
    # Проверяем формат файла
    if not (is_image_file(file_name) or is_video_file(file_name)):
        await message.reply_text(
            text=get_text(context, 'error_unsupported_format')
        )
        return WAITING_FOR_COMPRESS_FILE
    
    # Добавляем задачу в очередь
    queue_result = await compression_queue.add_task(
        user_id=user.id,
        task_func=process_compression_task,
        message=message,
        document=document,
        file_name=file_name,
        context=context
    )
    
    if not queue_result['success']:
        # Обработка ошибок очереди
        if queue_result['error'] == 'too_many_tasks':
            await message.reply_text(
                text=get_text(context, 'too_many_tasks')
            )
        elif queue_result['error'] == 'queue_full':
            await message.reply_text(
                text=get_text(context, 'queue_full', queue_size=queue_result.get('queue_size', 10))
            )
        else:
            await message.reply_text(
                text=get_text(context, 'error_processing')
            )
    else:
        # Задача успешно добавлена в очередь
        await message.reply_text(
            text=get_text(
                context,
                'queue_position',
                position=queue_result['position'],
                current=queue_result['current_tasks'],
                max=queue_result['max_concurrent']
            )
        )
        
        logger.info(f"User {user.id} added {file_name} to compression queue, position: {queue_result['position']}")
    
    return ConversationHandler.END
