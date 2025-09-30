#!/usr/bin/env python
"""
Главный файл бота с поддержкой webhook и async DB
"""

import os
import sys
import logging
import asyncio
from typing import Optional

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импорты проекта
import config
from database.async_db import init_async_db, close_async_db
from webhook_server import init_webhook_server
from handlers import *
from utils.error_handler import error_handler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Флаг для выбора режима (webhook или polling)
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'


async def post_init(application: Application) -> None:
    """Инициализация после запуска бота"""
    logger.info("Running post-initialization...")
    
    # Инициализируем async database
    try:
        db = await init_async_db(config.DATABASE_URL)
        application.bot_data['async_db'] = db
        logger.info("Async database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize async database: {e}")
    
    # Инициализируем Redis для кеширования (если нужно)
    if config.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            redis_client = await aioredis.from_url(
                config.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            application.bot_data['redis'] = redis_client
            logger.info("Redis client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
    
    # Инициализируем Keitaro веб-сервер (если настроен)
    if config.DATABASE_URL and 'async_db' in application.bot_data:
        try:
            from web_server import KeitaroWebServer
            keitaro_server = KeitaroWebServer(
                bot=application.bot,
                database=application.bot_data['async_db'],
                port=int(os.getenv('KEITARO_WEBHOOK_PORT', '8080'))
            )
            application.bot_data['keitaro_server'] = keitaro_server
            
            # Запускаем в отдельной задаче
            asyncio.create_task(run_keitaro_server(keitaro_server))
            logger.info("Keitaro webhook server started")
        except Exception as e:
            logger.warning(f"Keitaro module not available: {e}")
    
    logger.info("Post-initialization completed")


async def run_keitaro_server(server):
    """Запуск Keitaro сервера в фоне"""
    try:
        runner = web.AppRunner(server.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', server.port)
        await site.start()
        logger.info(f"Keitaro server running on port {server.port}")
    except Exception as e:
        logger.error(f"Failed to start Keitaro server: {e}")


async def post_shutdown(application: Application) -> None:
    """Очистка при остановке бота"""
    logger.info("Running post-shutdown...")
    
    # Закрываем async database
    if 'async_db' in application.bot_data:
        await close_async_db()
        logger.info("Async database closed")
    
    # Закрываем Redis
    if 'redis' in application.bot_data:
        await application.bot_data['redis'].close()
        logger.info("Redis connection closed")
    
    logger.info("Post-shutdown completed")


def main() -> None:
    """Главная функция"""
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    
    # ConversationHandler для уникализатора (с Celery)
    from handlers.uniqizer_async import (
        uniqueness_tool_callback_async,
        copies_input_handler,
        file_handler,
        wrong_media_handler,
        cancel_handler,
        main_menu_callback,
        WAITING_FOR_COPIES,
        WAITING_FOR_FILE
    )
    
    uniqueness_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(uniqueness_tool_callback_async, pattern="^uniqueness_tool$")],
        states={
            WAITING_FOR_COPIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, copies_input_handler),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            WAITING_FOR_FILE: [
                MessageHandler(filters.Document.ALL, file_handler),
                MessageHandler(filters.VIDEO | filters.PHOTO, wrong_media_handler),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(uniqueness_conv)
    
    # ConversationHandler для скрытия текста
    hide_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(hide_text_callback, pattern="^hide_text$")],
        states={
            WAITING_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(hide_text_conv)
    
    # ConversationHandler для умного сжатия (с Celery)
    compress_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(smart_compress_callback, pattern="^smart_compress$")],
        states={
            WAITING_FOR_COMPRESS_FILE: [
                MessageHandler(filters.Document.ALL, compress_file_handler),
                MessageHandler(filters.VIDEO | filters.PHOTO, wrong_media_handler_compress),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(compress_conv)
    
    # ConversationHandler для скачивания видео (с Celery)
    video_download_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(video_downloader_callback, pattern="^video_downloader$")],
        states={
            WAITING_FOR_VIDEO_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            WAITING_FOR_ACTION: [
                CallbackQueryHandler(action_handler, pattern="^(download_video|download_audio)$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_video_download),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(video_download_conv)
    
    # ROI калькулятор
    roi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(roi_calculator_callback, pattern="^roi_calculator$")],
        states={
            ROIStates.MENU.value: [
                CallbackQueryHandler(roi_start, pattern="^roi_start$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            ROIStates.INPUT_SPEND.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_spend)],
            ROIStates.INPUT_INCOME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_income)],
            ROIStates.INPUT_SHOWS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_shows)],
            ROIStates.INPUT_CLICKS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_clicks)],
            ROIStates.INPUT_LEADS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_leads)],
            ROIStates.INPUT_SALES.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_sales)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_roi),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(roi_conv)
    
    # Остальные обработчики
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Хуки инициализации
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # Запуск бота
    if USE_WEBHOOK:
        # Webhook mode
        logger.info("Starting bot in WEBHOOK mode...")
        
        webhook_domain = os.getenv('WEBHOOK_DOMAIN')
        if not webhook_domain:
            logger.error("WEBHOOK_DOMAIN not set!")
            return
        
        # Запускаем с webhook
        asyncio.run(run_with_webhook(application, webhook_domain))
    else:
        # Polling mode
        logger.info("Starting bot in POLLING mode...")
        application.run_polling(
            allowed_updates=['message', 'callback_query', 'edited_message']
        )


async def run_with_webhook(application: Application, domain: str):
    """Запуск бота с webhook"""
    from webhook_server import WebhookServer
    from aiohttp import web
    
    # Инициализируем приложение
    await application.initialize()
    await application.post_init(application)
    await application.start()
    
    # Создаем webhook сервер
    webhook_server = WebhookServer(
        bot_token=config.BOT_TOKEN,
        webhook_path='/telegram/webhook',
        port=8443
    )
    webhook_server.set_application(application)
    
    # Устанавливаем webhook
    await webhook_server.setup_webhook(domain=domain)
    
    # Запускаем сервер
    runner = web.AppRunner(webhook_server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8443)
    
    try:
        await site.start()
        logger.info("Webhook server started on port 8443")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("Stopping webhook server...")
    finally:
        await webhook_server.remove_webhook()
        await runner.cleanup()
        await application.stop()
        await application.shutdown()
        await application.post_shutdown(application)


if __name__ == '__main__':
    main()
