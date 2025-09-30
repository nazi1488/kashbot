"""
Обновленный обработчик уникализации с Celery
"""

import os
import logging
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from celery_app import app as celery_app
from tasks.video_tasks import process_video_uniqueness_task
from tasks.image_tasks import process_image_uniqueness_task
from utils.localization import get_text
from utils import is_video_file, is_image_file
import config

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_COPIES, WAITING_FOR_FILE = range(2)


async def uniqueness_tool_callback_async(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Уникализатор' с Celery"""
    query = update.callback_query
    await query.answer()
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', 'uniqueness_tool')
    
    text = get_text(context, 'copies_prompt')
    await query.edit_message_text(text=text)
    
    return WAITING_FOR_COPIES


async def process_media_file_async(
    message,
    document=None,
    file_obj=None,
    file_name: str = None,
    context: ContextTypes.DEFAULT_TYPE = None,
    is_compressed: bool = False
) -> int:
    """Обработчик медиафайлов через Celery"""
    
    user = message.from_user
    copies_count = context.user_data.get('copies_count', 3)
    
    # Определяем файл для обработки
    if document:
        file_to_process = document
        file_name = file_name or document.file_name
    else:
        file_to_process = file_obj
        
    # Проверяем размер
    if file_to_process.file_size > config.MAX_FILE_SIZE:
        max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
        await message.reply_text(text=get_text(context, 'error_file_too_large', max_size=max_size_mb))
        return WAITING_FOR_FILE
    
    # Определяем тип файла
    is_video = is_video_file(file_name)
    is_image = is_image_file(file_name)
    
    if not is_video and not is_image:
        await message.reply_text(text=get_text(context, 'error_unsupported_format'))
        return WAITING_FOR_FILE
    
    # Показываем уведомление о добавлении в очередь
    processing_msg = await message.reply_text(
        text="⏳ Файл добавлен в очередь обработки...\n"
             "📊 Проверяю загруженность системы..."
    )
    
    temp_dir = None
    
    try:
        # Скачиваем файл
        temp_dir = tempfile.mkdtemp(prefix=f"unique_{user.id}_")
        input_path = Path(temp_dir) / file_name
        
        file_download = await file_to_process.get_file()
        await file_download.download_to_drive(str(input_path))
        
        # Запускаем задачу в Celery
        if is_video:
            task = process_video_uniqueness_task.apply_async(
                args=[],
                kwargs={
                    'file_path': str(input_path),
                    'copies_count': copies_count,
                    'user_id': user.id,
                    'chat_id': message.chat_id,
                    'message_id': processing_msg.message_id,
                },
                queue='video',
                priority=5
            )
        else:
            task = process_image_uniqueness_task.apply_async(
                args=[],
                kwargs={
                    'file_path': str(input_path),
                    'copies_count': copies_count,
                    'user_id': user.id,
                    'chat_id': message.chat_id,
                    'message_id': processing_msg.message_id,
                },
                queue='image',
                priority=3
            )
        
        # Сохраняем task_id для отслеживания
        context.user_data[f'task_{task.id}'] = {
            'type': 'uniqueness',
            'file_type': 'video' if is_video else 'image',
            'temp_dir': temp_dir
        }
        
        # Обновляем сообщение с информацией о задаче
        await processing_msg.edit_text(
            text=f"✅ Задача добавлена в очередь!\n\n"
                 f"🆔 ID задачи: `{task.id[:8]}...`\n"
                 f"📁 Тип: {'Видео' if is_video else 'Изображение'}\n"
                 f"🔢 Копий: {copies_count}\n\n"
                 f"⏳ Ожидайте результат...\n"
                 f"💡 Вы можете продолжить использовать бота",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Запускаем асинхронный мониторинг задачи
        context.application.create_task(
            monitor_task_progress(
                task_id=task.id,
                message=message,
                processing_msg=processing_msg,
                context=context
            )
        )
        
    except Exception as e:
        logger.error(f"Error processing file for user {user.id}: {e}")
        
        # Очистка при ошибке
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        await processing_msg.edit_text(
            text=get_text(context, 'error_processing')
        )
    
    # Показываем кнопки для следующего действия
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


async def monitor_task_progress(
    task_id: str,
    message,
    processing_msg,
    context: ContextTypes.DEFAULT_TYPE
):
    """Мониторинг прогресса Celery задачи"""
    import asyncio
    from celery.result import AsyncResult
    
    try:
        task = AsyncResult(task_id, app=celery_app)
        last_status = None
        
        while not task.ready():
            # Получаем текущий статус
            if task.state == 'PROCESSING':
                info = task.info
                if info and info != last_status:
                    last_status = info
                    current = info.get('current', 0)
                    total = info.get('total', 0)
                    status = info.get('status', 'Обработка...')
                    
                    progress_text = f"⚙️ {status}\n"
                    if total > 0:
                        progress_bar = create_progress_bar(current, total)
                        progress_text += f"{progress_bar} {current}/{total}"
                    
                    try:
                        await processing_msg.edit_text(progress_text)
                    except:
                        pass  # Игнорируем ошибки редактирования
            
            await asyncio.sleep(2)  # Проверяем каждые 2 секунды
        
        # Задача завершена
        result = task.get()
        
        if result.get('success'):
            # Отправляем результат
            zip_path = result.get('zip_path')
            count = result.get('count', 0)
            
            if zip_path and os.path.exists(zip_path):
                await processing_msg.delete()
                
                with open(zip_path, 'rb') as zip_file:
                    await message.reply_document(
                        document=zip_file,
                        filename=f"unique_files_{count}.zip",
                        caption=get_text(context, 'success', count=count)
                    )
                
                # Очищаем временные файлы
                temp_dir = result.get('temp_dir')
                if temp_dir and os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # Ошибка
            error = result.get('error', 'Неизвестная ошибка')
            await processing_msg.edit_text(
                f"❌ Ошибка обработки: {error}\n\n"
                f"Попробуйте еще раз или обратитесь к администратору."
            )
        
        # Удаляем информацию о задаче
        context.user_data.pop(f'task_{task_id}', None)
        
    except Exception as e:
        logger.error(f"Error monitoring task {task_id}: {e}")
        await processing_msg.edit_text(
            text="❌ Ошибка отслеживания задачи. Проверьте результат позже."
        )


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создает прогресс-бар для отображения"""
    if total == 0:
        return "⬜" * length
    
    filled = int(length * current / total)
    bar = "🟩" * filled + "⬜" * (length - filled)
    percent = int(100 * current / total)
    
    return f"{bar} {percent}%"
