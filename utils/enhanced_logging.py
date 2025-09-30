"""
Улучшенное логирование с контекстом и фильтрацией
"""

import logging
import logging.handlers
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import sys
import os

from utils.error_handler import error_handler


class ContextFilter(logging.Filter):
    """Фильтр для добавления контекста в логи"""

    def __init__(self, context_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context_data = context_data or {}

    def filter(self, record):
        """Добавляем контекст к записи лога"""
        for key, value in self.context_data.items():
            setattr(record, key, value)
        return True


class TelegramBotFormatter(logging.Formatter):
    """Форматтер для логов телеграм бота"""

    def __init__(self, include_context: bool = True):
        self.include_context = include_context
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record):
        """Форматируем запись лога"""
        # Добавляем эмодзи для уровней логирования
        level_emojis = {
            'DEBUG': '🐛',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }

        # Заменяем имя уровня на эмодзи + текст
        original_levelname = record.levelname
        if record.levelname in level_emojis:
            record.levelname = f"{level_emojis[record.levelname]} {record.levelname}"

        # Добавляем контекст если доступен
        if self.include_context and hasattr(record, 'user_id'):
            context_info = []
            if hasattr(record, 'user_id'):
                context_info.append(f"User: {record.user_id}")
            if hasattr(record, 'chat_id'):
                context_info.append(f"Chat: {record.chat_id}")
            if hasattr(record, 'error_code'):
                context_info.append(f"Error: {record.error_code}")

            if context_info:
                record.msg = f"[{', '.join(context_info)}] {record.msg}"

        result = super().format(record)

        # Восстанавливаем оригинальное имя уровня
        record.levelname = original_levelname

        return result


class ErrorTrackingHandler(logging.Handler):
    """Обработчик для отслеживания ошибок"""

    def __init__(self):
        super().__init__()
        self.error_count = {}
        self.critical_errors = []

    def emit(self, record):
        """Обрабатываем запись лога"""
        if record.levelno >= logging.ERROR:
            # Отслеживаем количество ошибок
            error_key = f"{record.name}:{record.levelname}"
            current_time = datetime.now()

            if error_key in self.error_count:
                last_time, count = self.error_count[error_key]
                if (current_time - last_time).seconds < 300:  # 5 минут
                    count += 1
                    if count >= 10:  # 10 ошибок за 5 минут
                        self._handle_critical_error(record, error_key, count)
                else:
                    self.error_count[error_key] = (current_time, 1)
            else:
                self.error_count[error_key] = (current_time, 1)

    def _handle_critical_error(self, record, error_key, count):
        """Обработать критическую ситуацию с повторяющимися ошибками"""
        critical_error = {
            'error_key': error_key,
            'count': count,
            'first_seen': datetime.now(),
            'last_seen': datetime.now(),
            'message': record.getMessage(),
            'level': record.levelname
        }

        self.critical_errors.append(critical_error)

        # Уведомляем админа
        asyncio.create_task(
            error_handler._notify_admin({
                'error_type': 'REPEATED_ERRORS',
                'error_message': f"Critical error flood detected: {error_key} ({count} errors in 5 minutes)"
            }, repeated=True)
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "bot.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    include_context: bool = True
):
    """Настроить систему логирования"""

    # Создаем директорию для логов если нужно
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Удаляем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = TelegramBotFormatter(include_context=include_context)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Файловый обработчик с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = TelegramBotFormatter(include_context=include_context)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Обработчик для отслеживания ошибок
    error_tracker = ErrorTrackingHandler()
    error_tracker.setLevel(logging.WARNING)
    logger.addHandler(error_tracker)

    # Настраиваем логгеры для внешних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    return logger, error_tracker


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """Логировать сообщение с контекстом"""
    if context:
        # Создаем фильтр с контекстом
        context_filter = ContextFilter(context)
        logger.addFilter(context_filter)

    try:
        log_method = getattr(logger, level.lower())
        log_method(message, **kwargs)
    finally:
        # Убираем фильтр
        if context:
            logger.removeFilter(context_filter)


def create_error_report(error_tracker, include_critical: bool = True) -> str:
    """Создать отчет об ошибках"""
    report = []

    # Статистика ошибок
    report.append("📊 Отчет об ошибках\n")

    if error_tracker.error_count:
        report.append("🔄 Повторяющиеся ошибки:")
        for error_key, (last_time, count) in error_tracker.error_count.items():
            report.append(f"  • {error_key}: {count} раз")

    if include_critical and error_tracker.critical_errors:
        report.append("\n🚨 Критические ошибки:")
        for error in error_tracker.critical_errors[-5:]:  # Последние 5
            report.append(
                f"  • {error['error_key']}: {error['count']} ошибок\n"
                f"    Сообщение: {error['message'][:100]}..."
            )

    return "\n".join(report)


# Глобальные переменные для логирования
_bot_logger = None
_error_tracker = None


def get_logger() -> logging.Logger:
    """Получить настроенный логгер"""
    global _bot_logger
    if _bot_logger is None:
        _bot_logger, _error_tracker = setup_logging()
    return _bot_logger


def get_error_tracker():
    """Получить трекер ошибок"""
    global _error_tracker
    if _error_tracker is None:
        _, _error_tracker = setup_logging()
    return _error_tracker
