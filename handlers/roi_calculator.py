"""
Обработчик ROI-калькулятора для арбитражников
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from utils.localization import get_text
from .roi.states import ROIStates
from .roi.validators import validate_number
from .roi.metrics import ROIMetrics

logger = logging.getLogger(__name__)

# Константы для кнопок
SKIP_BUTTON = "⏭ Пропустить"
CANCEL_BUTTON = "❌ Отмена"

def get_input_keyboard():
    """Создает клавиатуру для ввода данных"""
    keyboard = [
        [KeyboardButton(SKIP_BUTTON)],
        [KeyboardButton(CANCEL_BUTTON)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def roi_calculator_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'ROI-калькулятор'"""
    query = update.callback_query
    await query.answer()
    
    # Трекаем событие
    if 'event_tracker' in context.bot_data:
        await context.bot_data['event_tracker'].track_event(update, context, 'command', 'roi_calculator')
    
    # Инициализируем данные пользователя
    context.user_data['roi_data'] = {}
    
    text = (
        "📊 **ROI-калькулятор арбитражника**\n\n"
        "💡 **Что это такое?**\n"
        "Этот калькулятор считает окупаемость трафика и базовые метрики. "
        "Вводи цифры по очереди. Если какой-то цифры нет — жми **Пропустить**.\n\n"
        "📈 **Что будем считать:**\n"
        "• ROI, профит, ROAS\n"
        "• CTR, CPC, CPA, CPM\n"
        "• Конверсии и средние чеки\n\n"
        "⚡ Займет 2 минуты, получишь полную картину!"
    )
    
    keyboard = [
        [InlineKeyboardButton("▶️ Начать расчет", callback_data='roi_start')],
        [InlineKeyboardButton("❌ Отмена", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ROIStates.MENU.value

async def roi_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинаем сбор данных - первый шаг (расход)"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "💰 **Шаг 1/6: Расход**\n\n"
        "Сколько потратил на рекламу? (в долларах)\n\n"
        "💡 *Примеры ввода:*\n"
        "`1500`, `1,500`, `1 500`, `1500.50`"
    )
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введи сумму расхода:",
        reply_markup=get_input_keyboard()
    )
    
    return ROIStates.INPUT_SPEND.value

async def input_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод расхода"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['spend'] = None
    else:
        is_valid, number, error = validate_number(text, "расход")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_SPEND.value
        context.user_data['roi_data']['spend'] = number
    
    # Переходим к следующему шагу
    text = (
        "💵 **Шаг 2/6: Доход**\n\n"
        "Сколько заработал с этого трафика?\n\n"
        "💡 *Это выручка от продаж, партнерские выплаты и т.д.*"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_input_keyboard())
    
    return ROIStates.INPUT_INCOME.value

async def input_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод дохода"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['income'] = None
    else:
        is_valid, number, error = validate_number(text, "доход")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_INCOME.value
        context.user_data['roi_data']['income'] = number
    
    # Переходим к следующему шагу
    text = (
        "👁 **Шаг 3/6: Показы**\n\n"
        "Сколько было показов рекламы?\n\n"
        "💡 *Impressions в рекламном кабинете*"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_input_keyboard())
    
    return ROIStates.INPUT_SHOWS.value

async def input_shows(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод показов"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['shows'] = None
    else:
        is_valid, number, error = validate_number(text, "показы")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_SHOWS.value
        context.user_data['roi_data']['shows'] = number
    
    # Переходим к следующему шагу
    text = (
        "👆 **Шаг 4/6: Клики**\n\n"
        "Сколько было кликов по рекламе?\n\n"
        "💡 *Clicks в статистике*"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_input_keyboard())
    
    return ROIStates.INPUT_CLICKS.value

async def input_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод кликов"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['clicks'] = None
    else:
        is_valid, number, error = validate_number(text, "клики")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_CLICKS.value
        context.user_data['roi_data']['clicks'] = number
    
    # Переходим к следующему шагу
    text = (
        "📝 **Шаг 5/6: Заявки (лиды)**\n\n"
        "Сколько человек оставили заявку/регистрацию?\n\n"
        "💡 *Leads, регистрации, заявки на консультацию и т.д.*"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_input_keyboard())
    
    return ROIStates.INPUT_LEADS.value

async def input_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод заявок"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['leads'] = None
    else:
        is_valid, number, error = validate_number(text, "заявки")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_LEADS.value
        context.user_data['roi_data']['leads'] = number
    
    # Переходим к следующему шагу
    text = (
        "💰 **Шаг 6/6: Продажи**\n\n"
        "Сколько человек купили/оплатили?\n\n"
        "💡 *Финальные конверсии: покупки, оплаченные заказы*"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_input_keyboard())
    
    return ROIStates.INPUT_SALES.value

async def input_sales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем ввод продаж и показываем результаты"""
    text = update.message.text
    
    if text == CANCEL_BUTTON:
        return await cancel_roi(update, context)
    
    if text == SKIP_BUTTON:
        context.user_data['roi_data']['sales'] = None
    else:
        is_valid, number, error = validate_number(text, "продажи")
        if not is_valid:
            await update.message.reply_text(error, reply_markup=get_input_keyboard())
            return ROIStates.INPUT_SALES.value
        context.user_data['roi_data']['sales'] = number
    
    # Убираем клавиатуру
    await update.message.reply_text(
        "🧮 Считаю метрики...", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Рассчитываем и показываем результаты
    return await show_results(update, context)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показываем результаты расчета"""
    roi_data = context.user_data.get('roi_data', {})
    
    # Создаем калькулятор и считаем метрики
    calculator = ROIMetrics(roi_data)
    results_card = calculator.format_results_card()
    
    # Кнопки под результатом
    keyboard = [
        [InlineKeyboardButton("🔁 Рассчитать заново", callback_data='roi_calculator')],
        [InlineKeyboardButton("🔙 В меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=results_card,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Очищаем данные
    context.user_data.pop('roi_data', None)
    
    logger.info(f"ROI calculation completed for user {update.effective_user.id}")
    
    return ConversationHandler.END

async def cancel_roi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяем расчет ROI"""
    # Очищаем данные
    context.user_data.pop('roi_data', None)
    
    await update.message.reply_text(
        "❌ Расчет ROI отменен", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Показываем главное меню
    from .subscription import show_main_menu
    await show_main_menu(update, context)
    
    return ConversationHandler.END
