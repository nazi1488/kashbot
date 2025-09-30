"""
Административные команды для управления ботом
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.queue_manager import compression_queue
import config

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику очереди (только для админов)"""
    user = update.effective_user
    
    # Проверяем, является ли пользователь администратором
    if user.id not in config.BOT_ADMINS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    # Получаем статистику
    stats = compression_queue.get_stats()
    
    # Формируем сообщение
    message = f"""📊 **Статистика очереди сжатия**

🔄 **Текущее состояние:**
• Размер очереди: {stats['queue_size']}
• Активных задач: {stats['current_tasks']}/{stats['max_concurrent']}
• Активных пользователей: {stats['active_users']}

📈 **Общая статистика:**
• Обработано: {stats['tasks_processed']}
• Ошибок: {stats['tasks_failed']}

💻 **Система:**
• Загрузка CPU: {stats['cpu_usage']:.1f}%
• Порог CPU: {compression_queue.cpu_threshold}%

⚙️ **Настройки:**
• Макс. параллельных задач: {compression_queue.max_concurrent_tasks}
• Макс. размер очереди: {compression_queue.max_queue_size}
• Таймаут задачи: {compression_queue.task_timeout}с
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')
    
    logger.info(f"Admin {user.id} requested queue stats")
