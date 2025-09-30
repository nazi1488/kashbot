#!/usr/bin/env python3
"""
Главный файл для запуска Telegram-бота уникализации медиафайлов
"""

import logging
import sys
import asyncio
import os
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# Добавляем текущую директорию в sys.path для корректного импорта
sys.path.insert(0, str(Path(__file__).parent))

import config
from utils import check_ffmpeg_installed, ensure_bot_can_check_subscription
from database import Database, EventTracker
from handlers import (
    start_command,
    language_callback,
    check_subscription_callback,
    start_uniqizer,
    copies_input_handler,
    file_handler,
    wrong_media_handler,
    cancel_handler,
    main_menu_callback,
    WAITING_FOR_COPIES,
    WAITING_FOR_FILE,
    hide_text_callback,
    text_handler,
    WAITING_FOR_TEXT,
    smart_compress_callback,
    compress_file_handler,
    wrong_media_handler_compress,
    WAITING_FOR_COMPRESS_FILE,
    roi_calculator_callback,
    roi_start,
    input_spend,
    input_income,
    input_shows,
    input_clicks,
    input_leads,
    input_sales,
    cancel_roi,
    ROIStates
)

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


async def error_handler(update: Update, context) -> None:
    """Обработчик ошибок"""
    from utils.error_handler import error_handler as error_processor

    try:
        user_id = update.effective_user.id if update and update.effective_user else None
        error_info = await error_processor.handle_error(update, context, context.error, user_id)

        # Отправляем сообщение пользователю только если есть update
        if update and update.effective_message:
            await error_processor.send_error_message(update, context, error_info)

        # Уведомляем админа если нужно
        if error_info['should_notify_admin']:
            await error_processor._notify_admin({
                'user_id': user_id,
                'error_type': type(context.error).__name__,
                'error_message': str(context.error)
            })

    except Exception as e:
        logger.error(f"Error in error handler: {e}")
        # Абсолютный fallback
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Произошла критическая ошибка. Пожалуйста, обратитесь к администратору."
                )
        except:
            pass


async def post_init(application: Application) -> None:
    """Инициализация после запуска бота"""
    bot = application.bot
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")
    
    # Проверяем, может ли бот проверять подписки
    error_msg = await ensure_bot_can_check_subscription(bot, config.CHANNEL_USERNAME)
    if error_msg:
        logger.warning(f"Subscription check warning: {error_msg}")
        logger.warning("Bot will work but subscription check will always pass!")
    
    # Инициализируем базу данных и трекер
    if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL:
        try:
            database = Database(config.DATABASE_URL)
            event_tracker = EventTracker(database)
            
            # Сохраняем в bot_data для доступа из обработчиков
            application.bot_data['database'] = database
            application.bot_data['event_tracker'] = event_tracker
            
            logger.info("Database and event tracker initialized successfully")
            
            # Закрываем старые сессии
            event_tracker.close_old_sessions()
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.warning("Bot will work without analytics")
    
    # Инициализируем Random Face если доступен
    if 'init_redis_for_random_face' in application.bot_data:
        try:
            await application.bot_data['init_redis_for_random_face']()
            
            # Сохраняем настройки для доступа из handlers
            from config import settings
            application.bot_data['FACE_QUOTA_PER_DAY'] = settings.FACE_QUOTA_PER_DAY
            
        except Exception as e:
            logger.error(f"Failed to initialize Random Face: {e}")
            logger.warning("Random Face will not be available")
    
    # Запускаем веб-сервер Keitaro если есть
    if 'keitaro_server' in application.bot_data:
        try:
            await application.bot_data['keitaro_server'].start()
            logger.info("Keitaro webhook server started")
        except Exception as e:
            logger.error(f"Failed to start Keitaro server: {e}")
            logger.warning("Keitaro webhooks will not be available")


def main() -> None:
    """Основная функция запуска бота"""
    # Проверяем наличие токена
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set it in .env file or environment variables")
        sys.exit(1)
    
    # Проверяем установку ffmpeg
    if not check_ffmpeg_installed():
        logger.error("FFmpeg not found! Please install ffmpeg to process videos.")
        logger.error("Install with: sudo apt-get install ffmpeg (Ubuntu/Debian)")
        logger.error("or: brew install ffmpeg (macOS)")
        sys.exit(1)
    
    # Создаем приложение
    builder = Application.builder().token(config.BOT_TOKEN)
    
    # Используем self-hosted API если настроено
    if config.USE_LOCAL_BOT_API:
        base_url = f"{config.LOCAL_BOT_API_URL}/bot{config.BOT_TOKEN}/"
        builder = builder.base_url(base_url).base_file_url(base_url)
        logger.info(f"Using self-hosted Bot API at {config.LOCAL_BOT_API_URL}")
    
    application = builder.build()
    
    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start_command))
    
    # Админская панель (если есть админы и база данных)
    if config.BOT_ADMINS and config.DATABASE_URL:
        try:
            from handlers.admin_panel import AdminPanel
            from handlers.admin import stats_command
            from database import Database
            
            # Создаем экземпляр админ панели
            db = Database(config.DATABASE_URL)
            admin_panel = AdminPanel(db)
            
            # Команда /admin
            async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await admin_panel.show_menu(update, context)
            
            application.add_handler(CommandHandler("admin", admin_command))
            application.add_handler(CommandHandler("stats", stats_command))
            
            # Обработчики callback для админ панели
            application.add_handler(CallbackQueryHandler(admin_panel.show_metrics, pattern="^admin_metrics$"))
            application.add_handler(CallbackQueryHandler(admin_panel.show_detailed_analytics, pattern="^admin_detailed$"))
            application.add_handler(CallbackQueryHandler(admin_panel.show_users_info, pattern="^admin_users$"))
            application.add_handler(CallbackQueryHandler(admin_panel.show_system_status, pattern="^admin_status$"))
            application.add_handler(CallbackQueryHandler(admin_panel.show_cookies_menu, pattern="^admin_cookies$"))
            application.add_handler(CallbackQueryHandler(admin_panel.cleanup_cookies, pattern="^cleanup_cookies$"))
            application.add_handler(CallbackQueryHandler(admin_panel.show_menu, pattern="^admin_menu$"))
            
            # Обработчики удаления cookies
            application.add_handler(CallbackQueryHandler(admin_panel.delete_cookies_menu, pattern="^delete_cookies_menu$"))
            application.add_handler(CallbackQueryHandler(admin_panel.delete_platform_cookies, pattern="^delete_platform_"))
            application.add_handler(CallbackQueryHandler(admin_panel.delete_single_cookie, pattern="^delete_single_"))
            application.add_handler(CallbackQueryHandler(admin_panel.delete_all_platform_cookies, pattern="^delete_all_"))
            
            # ConversationHandler для рассылки
            broadcast_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(admin_panel.start_broadcast, pattern="^admin_broadcast$")],
                states={
                    admin_panel.BROADCAST_TYPE: [
                        MessageHandler(filters.ALL & ~filters.COMMAND, admin_panel.receive_broadcast_content),
                        CallbackQueryHandler(admin_panel.show_menu, pattern="^admin_menu$"),
                        # Добавляем обработчик для повторного запуска рассылки
                        CallbackQueryHandler(admin_panel.start_broadcast, pattern="^admin_broadcast$")
                    ]
                },
                fallbacks=[
                    CallbackQueryHandler(admin_panel.cancel_broadcast, pattern="^broadcast_cancel$"),
                    CommandHandler("cancel", admin_panel.cancel_broadcast)
                ],
                per_user=True
            )
            application.add_handler(broadcast_conv)
            
            # Обработчик подтверждения рассылки
            application.add_handler(CallbackQueryHandler(admin_panel.send_broadcast, pattern="^broadcast_(send|cancel)$"))
            application.add_handler(CallbackQueryHandler(admin_panel.segment_selected, pattern="^segment_"))
            
            # ConversationHandler для добавления cookies
            cookies_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(admin_panel.add_cookies_start, pattern="^add_cookies_")],
                states={
                    admin_panel.COOKIES_INPUT: [
                        MessageHandler((filters.TEXT | filters.Document.ALL) & ~filters.COMMAND, admin_panel.process_cookies_input),
                        CallbackQueryHandler(admin_panel.show_cookies_menu, pattern="^admin_cookies$")
                    ]
                },
                fallbacks=[
                    CallbackQueryHandler(admin_panel.show_cookies_menu, pattern="^admin_cookies$"),
                    CommandHandler("cancel", lambda u, c: ConversationHandler.END),
                    MessageHandler(filters.ALL, admin_panel.process_cookies_input)  # Fallback for any other message type
                ],
                per_user=True
            )
            application.add_handler(cookies_conv)
            
            logger.info("Admin panel initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize admin panel: {e}")
            # Fallback to simple stats command
            from handlers.admin import stats_command
            application.add_handler(CommandHandler("stats", stats_command))
    
    # Создаем ConversationHandler для процесса уникализации
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_uniqizer, pattern="^uniqueness_tool$")],
        states={
            WAITING_FOR_FILE: [
                MessageHandler(filters.Document.ALL, file_handler),
                MessageHandler(filters.VIDEO | filters.PHOTO, wrong_media_handler),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            WAITING_FOR_COPIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, copies_input_handler),
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
    
    # Регистрируем обработчики
    application.add_handler(conv_handler)
    
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
    
    # ConversationHandler для умного сжатия
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
    
    # ConversationHandler для скачивания видео
    from handlers.video_download import (
        video_downloader_callback, 
        url_handler, 
        action_handler,
        cancel_video_download,
        WAITING_FOR_VIDEO_URL, 
        WAITING_FOR_ACTION
    )
    
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
    
    # Обработчики TOTP (2FA Generator)
    from handlers.totp_handler import (
        totp_menu_callback,
        totp_generate_new_callback, 
        totp_custom_secret_callback,
        totp_refresh_callback,
        totp_refresh_custom_callback,
        totp_auto_refresh_callback,
        totp_auto_refresh_custom_callback,
        totp_generate_qr_callback,
        totp_stop_auto_refresh_callback,
        totp_text_handler
    )
    
    # Регистрируем обработчики TOTP
    application.add_handler(CallbackQueryHandler(totp_menu_callback, pattern="^totp_menu$"))
    application.add_handler(CallbackQueryHandler(totp_generate_new_callback, pattern="^totp_generate_new$"))
    application.add_handler(CallbackQueryHandler(totp_custom_secret_callback, pattern="^totp_custom_secret$"))
    application.add_handler(CallbackQueryHandler(totp_refresh_callback, pattern="^totp_refresh$"))
    application.add_handler(CallbackQueryHandler(totp_refresh_custom_callback, pattern="^totp_refresh_custom$"))
    application.add_handler(CallbackQueryHandler(totp_auto_refresh_callback, pattern="^totp_auto_refresh$"))
    application.add_handler(CallbackQueryHandler(totp_auto_refresh_custom_callback, pattern="^totp_auto_refresh_custom$"))
    application.add_handler(CallbackQueryHandler(totp_generate_qr_callback, pattern="^totp_generate_qr$"))
    application.add_handler(CallbackQueryHandler(totp_stop_auto_refresh_callback, pattern="^totp_stop_auto_refresh$"))
    
    # Обработчики Gmail-алиасов
    from handlers.gmail_aliases import (
        gmail_menu_callback,
        gmail_generate_callback, 
        gmail_continue_callback,
        gmail_text_handler
    )
    
    # Регистрируем обработчики Gmail-алиасов
    application.add_handler(CallbackQueryHandler(gmail_menu_callback, pattern="^gmail_menu$"))
    application.add_handler(CallbackQueryHandler(gmail_generate_callback, pattern="^gmail_generate$"))
    application.add_handler(CallbackQueryHandler(gmail_continue_callback, pattern="^gmail_continue_"))
    
    # Обработчики KashMail
    from handlers.kashmail import (
        kashmail_menu_callback,
        kashmail_generate_callback,
        kashmail_stop_wait_callback,
        kashmail_burn_callback,
        kashmail_check_messages_callback,
        kashmail_show_body_callback,
        kashmail_show_links_callback,
        cleanup_kashmail
    )
    
    # Регистрируем обработчики KashMail
    application.add_handler(CallbackQueryHandler(kashmail_menu_callback, pattern="^kashmail_menu$"))
    application.add_handler(CallbackQueryHandler(kashmail_generate_callback, pattern="^kashmail_generate$"))
    application.add_handler(CallbackQueryHandler(kashmail_stop_wait_callback, pattern="^kashmail_stop_wait$"))
    application.add_handler(CallbackQueryHandler(kashmail_burn_callback, pattern="^kashmail_burn$"))
    application.add_handler(CallbackQueryHandler(kashmail_check_messages_callback, pattern="^kashmail_check$"))
    application.add_handler(CallbackQueryHandler(kashmail_show_body_callback, pattern="^kashmail_show_"))
    application.add_handler(CallbackQueryHandler(kashmail_show_links_callback, pattern="^kashmail_links_"))
    
    # Обработчики Random Face
    try:
        from infra.redis import redis_manager
        from features.random_face.handlers import register_random_face_handlers
        
        # Инициализируем Redis в post_init
        async def init_redis_for_random_face():
            redis_client = await redis_manager.initialize()
            register_random_face_handlers(application, redis_client)
            logger.info("Random Face handlers registered successfully")
        
        # Добавляем в контекст для post_init
        application.bot_data['init_redis_for_random_face'] = init_redis_for_random_face
        
    except ImportError as e:
        logger.warning(f"Random Face module not available: {e}")
    except Exception as e:
        logger.error(f"Error setting up Random Face: {e}")
    
    # ConversationHandler для ROI-калькулятора
    roi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(roi_calculator_callback, pattern="^roi_calculator$")],
        states={
            ROIStates.MENU.value: [
                CallbackQueryHandler(roi_start, pattern="^roi_start$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            ROIStates.INPUT_SPEND.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_spend)
            ],
            ROIStates.INPUT_INCOME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_income)
            ],
            ROIStates.INPUT_SHOWS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_shows)
            ],
            ROIStates.INPUT_CLICKS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_clicks)
            ],
            ROIStates.INPUT_LEADS.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_leads)
            ],
            ROIStates.INPUT_SALES.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_sales)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_roi),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_user=True,
        per_chat=True
    )
    application.add_handler(roi_conv)
    
    # Регистрируем Keitaro интеграцию
    try:
        from features.keitaro.handlers import register_keitaro_handlers
        
        if config.DATABASE_URL:
            db_for_keitaro = Database(config.DATABASE_URL) if 'db' not in locals() else db
            register_keitaro_handlers(application, db_for_keitaro)
            logger.info("Keitaro handlers registered successfully")
            
            # Запускаем веб-сервер для приема postback
            from web_server import KeitaroWebServer
            keitaro_server = KeitaroWebServer(
                bot=application.bot, 
                database=db_for_keitaro,
                port=int(os.getenv('KEITARO_WEBHOOK_PORT', '8080'))
            )
            application.bot_data['keitaro_server'] = keitaro_server
            
            # Домен для webhook URL
            application.bot_data['webhook_domain'] = os.getenv('WEBHOOK_DOMAIN', 'YOUR_DOMAIN')
            
    except ImportError as e:
        logger.warning(f"Keitaro module not available: {e}")
    except Exception as e:
        logger.error(f"Error setting up Keitaro: {e}")
    
    # Создаем единый обработчик текста
    async def unified_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Единый обработчик текстовых сообщений"""
        try:
            # Проверяем состояние Gmail-алиасов
            if (context.user_data.get('awaiting_gmail_input') or 
                context.user_data.get('awaiting_gmail_count_input')):
                await gmail_text_handler(update, context)
                return
            
            # Проверяем состояние TOTP
            if context.user_data.get('awaiting_totp_secret'):
                await totp_text_handler(update, context)
                return
            
            # Если никто не ожидает ввода, игнорируем
            
        except Exception as e:
            logger.error(f"Error in unified text handler: {e}")
    
    # Обработчик текста (единый для всех модулей)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        unified_text_handler,
        block=False
    ))
    
    # Обработчики callback-кнопок вне ConversationHandler
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Инициализация после запуска
    application.post_init = post_init
    
    # Запускаем бота
    logger.info("Starting bot...")
    
    async def cleanup_resources():
        """Асинхронная очистка ресурсов"""
        try:
            await cleanup_kashmail()
            from workers.kashmail_watcher import cleanup_watcher_service
            await cleanup_watcher_service()
            
            # Закрываем Redis подключение
            try:
                from infra.redis import redis_manager
                await redis_manager.close()
            except Exception as e:
                logger.error(f"Error closing Redis: {e}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    try:
        application.run_polling(drop_pending_updates=True)
    finally:
        # Очистка ресурсов при завершении
        try:
            asyncio.run(cleanup_resources())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
