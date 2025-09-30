"""
Обработчик для скачивания видео из социальных сетей с поддержкой ротации cookies
"""

import os
import logging
import tempfile
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from utils.localization import get_text
from utils.video_downloader_v2 import EnhancedVideoDownloader
from utils.cookies_manager import CookiesManager
from utils.queue_manager import compression_queue
from database import Database
import config

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_VIDEO_URL, WAITING_FOR_ACTION = range(2)

# Инициализируем компоненты
db = None
cookies_manager = None
video_downloader = None

# Инициализация при импорте
try:
    if config.DATABASE_URL:
        db = Database(config.DATABASE_URL)
        cookies_manager = CookiesManager(db)
        video_downloader = EnhancedVideoDownloader(
            cookies_manager=cookies_manager,
            db=db,
            max_file_size=config.MAX_FILE_SIZE
        )
        logger.info("Enhanced video downloader initialized with cookies manager")
    else:
        # Fallback на старый загрузчик без БД
        from utils.video_downloader import VideoDownloader
        video_downloader = VideoDownloader(max_file_size=config.MAX_FILE_SIZE)
        logger.warning("Using basic video downloader without cookies rotation")
except Exception as e:
    logger.error(f"Error initializing video downloader: {e}")
    # Используем базовый загрузчик
    from utils.video_downloader import VideoDownloader
    video_downloader = VideoDownloader(max_file_size=config.MAX_FILE_SIZE)


async def video_downloader_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Скачать видео'"""
    query = update.callback_query
    await query.answer()
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', 'video_downloader')
    
    # Отправляем объяснение с динамическим размером
    max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
    text = get_text(context, 'video_downloader_explanation', max_size=max_size_mb)
    await query.message.reply_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Показываем кнопку отмены
    keyboard = [[InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Просим отправить ссылку
    await query.message.reply_text(
        text=get_text(context, 'send_video_url'),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_VIDEO_URL


async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик полученной ссылки на видео"""
    message = update.message
    url = message.text.strip()
    
    # Проверяем, что это похоже на URL
    if not url.startswith(('http://', 'https://')):
        await message.reply_text(
            text=get_text(context, 'invalid_url'),
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_VIDEO_URL
    
    # Определяем платформу
    platform = video_downloader.detect_platform(url)
    if not platform:
        await message.reply_text(
            text=get_text(context, 'unsupported_platform'),
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_VIDEO_URL
    
    # Сохраняем URL и платформу
    context.user_data['video_url'] = url
    context.user_data['video_platform'] = platform
    
    # Предлагаем выбор действия
    keyboard = [
        [
            InlineKeyboardButton(get_text(context, 'download_video'), callback_data="download_video"),
            InlineKeyboardButton(get_text(context, 'download_audio'), callback_data="download_audio")
        ],
        [
            InlineKeyboardButton(get_text(context, 'back'), callback_data="main_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text=get_text(context, 'choose_video_action', platform=platform),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_ACTION


async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбранного действия"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    url = context.user_data.get('video_url')
    platform = context.user_data.get('video_platform')
    
    if not url:
        await query.message.reply_text(
            text=get_text(context, 'error_no_url')
        )
        return ConversationHandler.END
    
    # Показываем сообщение о начале обработки
    processing_msg = await query.message.reply_text(
        text=get_text(context, 'downloading_video', platform=platform)
    )
    
    try:
        if action == "download_video":
            await download_video_task(query.message, url, platform, context, processing_msg)
            
        elif action == "download_audio":
            await download_audio_task(query.message, url, platform, context, processing_msg)
            
            
        elif action == "main_menu":
            await processing_msg.delete()
            from .subscription import show_main_menu
            await show_main_menu(update, context)
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error in action_handler: {e}")
        await processing_msg.edit_text(
            text=get_text(context, 'error_downloading')
        )
    
    # Показываем главное меню
    keyboard = [[
        InlineKeyboardButton(get_text(context, 'video_downloader'), callback_data='video_downloader'),
        InlineKeyboardButton(get_text(context, 'main_menu'), callback_data='main_menu')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        text=get_text(context, 'download_more_or_menu'),
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


async def download_video_task(message, url: str, platform: str, context: ContextTypes.DEFAULT_TYPE, 
                              processing_msg):
    """Задача для скачивания видео с автоматической ротацией cookies"""
    temp_dir = None
    
    try:
        # Создаем временную директорию
        temp_dir = tempfile.mkdtemp()
        
        # Скачиваем видео
        await processing_msg.edit_text(
            text=get_text(context, 'downloading_in_progress')
        )
        
        # Получаем user_id для логирования
        user_id = message.from_user.id if message.from_user else None
        
        # Используем асинхронный метод с прогресс-трекингом
        if hasattr(video_downloader, 'download_video_async'):
            # Используем новый асинхронный метод с прогрессом
            video_path, error = await video_downloader.download_video_async(
                url=url,
                message=processing_msg,
                output_dir=temp_dir,
                user_id=user_id
            )
        elif hasattr(video_downloader, 'download_video_with_retry'):
            # Используем улучшенный загрузчик с ротацией
            video_path, error = await video_downloader.download_video_with_retry(
                url=url,
                user_id=user_id,
                output_dir=temp_dir
            )
        else:
            # Fallback на старый метод
            loop = asyncio.get_event_loop()
            video_path, error = await loop.run_in_executor(
                None,
                video_downloader.download_video,
                url,
                temp_dir
            )
        
        if error:
            # Если используется новый асинхронный метод, сообщение уже обновлено
            if not hasattr(video_downloader, 'download_video_async'):
                # Проверяем, является ли ошибка связанной с авторизацией
                if cookies_manager and any(word in error.lower() for word in ['приватное', 'private', 'авторизац']):
                    await processing_msg.edit_text(
                        text=f"❌ {error}\n\n💡 Попробуйте позже или обратитесь к администратору для обновления доступа."
                    )
                else:
                    await processing_msg.edit_text(
                        text=f"❌ {error}"
                    )
            return
        
        if video_path and os.path.exists(video_path):
            # Проверяем размер файла
            file_size = os.path.getsize(video_path)
            
            await processing_msg.edit_text(
                text=get_text(context, 'uploading_video')
            )
            
            # Отправляем видео
            with open(video_path, 'rb') as video_file:
                # Если файл больше 50MB, отправляем как документ
                LARGE_FILE_LIMIT = 50 * 1024 * 1024  # 50MB для отправки как документ
                if file_size > LARGE_FILE_LIMIT:
                    await message.reply_document(
                        document=video_file,
                        filename=os.path.basename(video_path),
                        caption=get_text(context, 'video_downloaded_large', 
                                       platform=platform, 
                                       size_mb=file_size // 1024 // 1024)
                    )
                else:
                    await message.reply_video(
                        video=video_file,
                        caption=get_text(context, 'video_downloaded', 
                                       platform=platform)
                    )
            
            # Удаляем сообщение о процессе только если не используется новый метод
            if not hasattr(video_downloader, 'download_video_async'):
                await processing_msg.delete()
            
            # Логируем успешное скачивание
            logger.info(f"Successfully downloaded video from {platform}: {url}")
        else:
            # Обновляем сообщение только если не используется новый метод
            if not hasattr(video_downloader, 'download_video_async'):
                await processing_msg.edit_text(
                    text=get_text(context, 'error_downloading')
                )
            
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        await processing_msg.edit_text(
            text=get_text(context, 'error_downloading')
        )
    finally:
        # Очищаем временные файлы
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


async def download_audio_task(message, url: str, platform: str, context: ContextTypes.DEFAULT_TYPE, processing_msg):
    """Задача для скачивания аудио"""
    temp_dir = None
    
    try:
        # Создаем временную директорию
        temp_dir = tempfile.mkdtemp()
        
        # Скачиваем аудио
        await processing_msg.edit_text(
            text=get_text(context, 'extracting_audio')
        )
        
        # Получаем user_id для логирования
        user_id = message.from_user.id if message.from_user else None
        
        # Проверяем тип загрузчика и вызываем соответствующий метод
        if hasattr(video_downloader, 'download_audio') and asyncio.iscoroutinefunction(video_downloader.download_audio):
            # Используем асинхронный метод EnhancedVideoDownloader
            audio_path, error = await video_downloader.download_audio(
                url=url,
                user_id=user_id,
                output_dir=temp_dir
            )
        else:
            # Используем синхронный метод в отдельном потоке
            loop = asyncio.get_event_loop()
            audio_path, error = await loop.run_in_executor(
                None,
                video_downloader.download_audio,
                url,
                temp_dir
            )
        
        if error:
            await processing_msg.edit_text(
                text=f"❌ {error}"
            )
            return
        
        if audio_path and os.path.exists(audio_path):
            await processing_msg.edit_text(
                text=get_text(context, 'uploading_audio')
            )
            
            # Отправляем аудио
            with open(audio_path, 'rb') as audio_file:
                await message.reply_audio(
                    audio=audio_file,
                    caption=get_text(context, 'audio_extracted', platform=platform),
                    title=os.path.basename(audio_path).replace('.mp3', '')
                )
            
            # Удаляем сообщение о процессе
            await processing_msg.delete()
            
            logger.info(f"Successfully extracted audio from {platform}: {url}")
        else:
            await processing_msg.edit_text(
                text=get_text(context, 'error_extracting_audio')
            )
            
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        await processing_msg.edit_text(
            text=get_text(context, 'error_extracting_audio')
        )
    finally:
        # Очищаем временные файлы
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


async def cancel_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена скачивания видео"""
    # Очищаем user_data
    context.user_data.pop('video_url', None)
    context.user_data.pop('video_platform', None)
    
    # Возвращаемся в главное меню
    from .subscription import show_main_menu
    await show_main_menu(update, context)
    
    return ConversationHandler.END
