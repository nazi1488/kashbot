"""
Шаблоны сообщений для событий Keitaro
"""

from typing import Dict, Any
import html


def escape_html(text: str) -> str:
    """Экранирует HTML символы"""
    if not text:
        return ""
    return html.escape(str(text))


def normalize_status(status: str) -> str:
    """Нормализует статус события"""
    status_lower = status.lower()
    
    # Маппинг статусов
    registration_statuses = {"registration", "lead", "signup", "register"}
    deposit_statuses = {"deposit", "sale", "ftd", "purchase", "payment"}
    reject_statuses = {"reject", "rejected", "trash", "refuse"}
    
    if status_lower in registration_statuses:
        return "registration"
    elif status_lower in deposit_statuses:
        return "deposit"
    elif status_lower in reject_statuses:
        return "rejected"
    else:
        return "registration"  # По умолчанию


def format_amount(revenue: str, payout: str, currency: str) -> str:
    """Форматирует сумму для отображения"""
    amount = revenue or payout or "0"
    
    # Убираем лишние нули после точки
    try:
        amount_float = float(amount)
        if amount_float == int(amount_float):
            amount = str(int(amount_float))
        else:
            amount = f"{amount_float:.2f}"
    except:
        pass
    
    if currency:
        return f"{amount} {currency}"
    return amount


def get_message_template(event_data: Dict[str, Any]) -> str:
    """
    Возвращает отформатированное сообщение для события
    
    Args:
        event_data: Словарь с данными события от Keitaro
        
    Returns:
        str: HTML-форматированное сообщение для Telegram
    """
    status = normalize_status(event_data.get('status', ''))
    
    # Получаем transaction ID
    tx = event_data.get('transaction_id') or event_data.get('click_id', '')
    if event_data.get('no_tx'):
        tx = f"{tx[:8]}... (generated)"
    
    # Экранируем все значения
    campaign_name = escape_html(event_data.get('campaign_name', ''))
    offer_name = escape_html(event_data.get('offer_name', ''))
    country = escape_html(event_data.get('country', ''))
    sub_id_1 = escape_html(event_data.get('sub_id_1', ''))
    creative_id = escape_html(event_data.get('creative_id', ''))
    landing_name = escape_html(event_data.get('landing_name', ''))
    source = escape_html(event_data.get('source', ''))
    tx_escaped = escape_html(tx)
    
    # Выбираем шаблон по статусу
    if status == "registration":
        message = f"""📝 <b>Регистрация</b>
Кампания: <code>{campaign_name or 'N/A'}</code>
Оффер: <code>{offer_name or landing_name or 'N/A'}</code>
ГЕО: <code>{country or 'N/A'}</code>"""
        
        if source:
            message += f"\nИсточник: <code>{source}</code>"
        if sub_id_1:
            message += f"\nSub1: <code>{sub_id_1}</code>"
        if tx_escaped:
            message += f"\nTX: <code>{tx_escaped}</code>"
    
    elif status == "deposit":
        amount = format_amount(
            event_data.get('conversion_revenue', ''),
            event_data.get('payout', ''),
            event_data.get('currency', '')
        )
        amount_escaped = escape_html(amount)
        
        message = f"""💰 <b>Депозит</b>
Кампания: <code>{campaign_name or 'N/A'}</code>"""
        
        if creative_id:
            message += f"\nКреатив: <code>{creative_id}</code>"
        
        message += f"""
Лендинг: <code>{offer_name or landing_name or 'N/A'}</code>
Доход: <b>{amount_escaped}</b>"""
        
        if sub_id_1:
            message += f"\nSub1: <code>{sub_id_1}</code>"
        if country:
            message += f" | GEO: <code>{country}</code>"
        if tx_escaped:
            message += f"\nTX: <code>{tx_escaped}</code>"
    
    elif status == "rejected":
        reason = escape_html(event_data.get('sub_id_2', ''))  # Часто причина в sub_id_2
        
        message = f"""⛔️ <b>Отказ</b>
Кампания: <code>{campaign_name or 'N/A'}</code>"""
        
        if reason:
            message += f"\nПричина: <code>{reason}</code>"
        if tx_escaped:
            message += f"\nTX: <code>{tx_escaped}</code>"
    
    else:
        # Универсальный шаблон для неизвестных статусов
        message = f"""📌 <b>{escape_html(event_data.get('status', 'Событие'))}</b>
Кампания: <code>{campaign_name or 'N/A'}</code>
Оффер: <code>{offer_name or 'N/A'}</code>"""
        
        if country:
            message += f"\nГЕО: <code>{country}</code>"
        if tx_escaped:
            message += f"\nTX: <code>{tx_escaped}</code>"
    
    # Добавляем дополнительные sub_id если есть
    extra_subs = []
    for i in range(2, 11):
        sub_val = event_data.get(f'sub_id_{i}')
        if sub_val and sub_val.strip():
            extra_subs.append(f"s{i}:{escape_html(sub_val)}")
    
    if extra_subs and len(extra_subs) <= 3:
        message += f"\n📎 {' | '.join(extra_subs)}"
    
    return message


def get_test_message() -> str:
    """Возвращает тестовое сообщение"""
    test_data = {
        'status': 'deposit',
        'transaction_id': 'test_' + str(hash('test'))[:8],
        'campaign_name': 'Test Campaign',
        'offer_name': 'Test Offer',
        'creative_id': 'cr_123',
        'conversion_revenue': '100',
        'currency': 'USD',
        'country': 'US',
        'sub_id_1': 'test_sub'
    }
    return get_message_template(test_data)
