# 📩 KashMail - Временная почта

KashMail - это модуль для создания временных email адресов и получения писем прямо в Telegram боте с использованием Mail.tm API.

## 🎯 Основные возможности

- **Генерация временных email адресов** - создание приватных адресов на базе Mail.tm
- **Мониторинг входящих писем** - автоматическое отслеживание новых сообщений
- **Извлечение OTP кодов** - автоматическое обнаружение кодов верификации
- **Извлечение ссылок** - парсинг и очистка ссылок из писем
- **Многоязычность** - поддержка RU/UA/EN локализации
- **Система лимитов** - контроль использования с дневными квотами
- **GDPR совместимость** - контент писем не сохраняется

## 🏗️ Архитектура

### Компоненты системы

```
services/
├── kashmail_api.py          # API клиент для Mail.tm
repos/
├── kashmail_sessions.py     # Репозиторий для сессий и счетчиков
handlers/
├── kashmail.py              # Telegram обработчики
workers/
├── kashmail_watcher.py      # Фоновый мониторинг писем
utils/
├── otp_extract.py           # Извлечение OTP кодов и ссылок
database/
├── models.py                # Модели БД (KashmailSession, KashmailDailyCounter)
```

### Схема БД

```sql
-- Сессии временных адресов
CREATE TABLE kashmail_sessions (
  user_id BIGINT PRIMARY KEY,
  address TEXT NOT NULL,
  jwt TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);

-- Дневные счетчики использования
CREATE TABLE kashmail_daily_counters (
  user_id BIGINT NOT NULL,
  day DATE NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);
```

## ⚙️ Конфигурация

### Переменные окружения

```bash
# Таймаут ожидания писем (секунды)
KASHMAIL_WAIT_TIMEOUT=200

# Базовый интервал поллинга (секунды)
KASHMAIL_POLL_BASE_SEC=2

# Максимальный интервал поллинга (секунды)
KASHMAIL_POLL_MAX_SEC=5

# Включение дневного лимита
KASHMAIL_ENABLE_DAILY_LIMIT=true

# Количество адресов в день на пользователя
KASHMAIL_DAILY_LIMIT=10
```

### Настройки в config.py

```python
# Настройки KashMail
KASHMAIL_WAIT_TIMEOUT = int(os.getenv("KASHMAIL_WAIT_TIMEOUT", "200"))
KASHMAIL_POLL_BASE_SEC = int(os.getenv("KASHMAIL_POLL_BASE_SEC", "2"))
KASHMAIL_POLL_MAX_SEC = int(os.getenv("KASHMAIL_POLL_MAX_SEC", "5"))
KASHMAIL_ENABLE_DAILY_LIMIT = os.getenv("KASHMAIL_ENABLE_DAILY_LIMIT", "true").lower() == "true"
KASHMAIL_DAILY_LIMIT = int(os.getenv("KASHMAIL_DAILY_LIMIT", "10"))
```

## 🚀 Установка и запуск

### 1. Установка зависимостей

```bash
pip install beautifulsoup4==4.12.2  # для парсинга HTML
```

### 2. Применение миграций БД

```bash
alembic upgrade head
```

### 3. Интеграция в main.py

Обработчики уже интегрированы в `main.py`:

```python
# Обработчики KashMail
from handlers.kashmail import (
    kashmail_menu_callback,
    kashmail_generate_callback,
    kashmail_copy_callback,
    kashmail_wait_callback,
    kashmail_stop_wait_callback,
    kashmail_burn_callback,
    kashmail_check_messages_callback,
    cleanup_kashmail
)

# Регистрация обработчиков
application.add_handler(CallbackQueryHandler(kashmail_menu_callback, pattern="^kashmail_menu$"))
application.add_handler(CallbackQueryHandler(kashmail_generate_callback, pattern="^kashmail_generate$"))
# ... остальные обработчики
```

## 📱 Пользовательский интерфейс

### Главное меню
- Кнопка "📩 KashMail" добавлена в главное меню бота

### Меню KashMail
- **📧 Сгенерировать временный email** - создание нового адреса
- **📋 Скопировать email** - копирование активного адреса
- **⏱ Ждать письмо (200 сек)** - запуск мониторинга
- **🔍 Проверить письма** - ручная проверка
- **🔥 Сжечь адрес** - завершение сессии

### Уведомления о письмах
При получении письма пользователь получает карточку с:
- Отправителем, темой и датой
- Автоматически извлеченными OTP кодами
- Кнопками для просмотра содержимого и ссылок

## 🔧 API клиент (MailTmApi)

### Основные методы

```python
api = MailTmApi(timeout_seconds=30)

# Получение доменов
domains = await api.get_domains()

# Создание аккаунта
email, password, account_id = await api.create_account(domain)

# Получение JWT токена
jwt_token = await api.get_jwt_token(email, password)

# Получение сообщений
messages = await api.get_messages(jwt_token)

# Получение деталей сообщения
message_detail = await api.get_message_detail(message_id, jwt_token)

# Создание полного временного email
email, jwt_token, expires_at = await api.create_temporary_email()

await api.close()
```

### Обработка ошибок
- **Rate limiting (429)**: экспоненциальный бэкофф с джиттером
- **Серверные ошибки (5xx)**: автоматические повторы
- **Таймауты**: настраиваемые лимиты времени

## 📊 Репозиторий сессий (KashmailRepository)

### Управление сессиями

```python
repo = KashmailRepository(database)

# Создание сессии
await repo.sessions.create_session(user_id, address, jwt, expires_at)

# Получение активной сессии
session = await repo.sessions.get_session(user_id)

# Обновление статуса
await repo.sessions.update_session_status(user_id, 'waiting')

# Сжигание сессии
await repo.sessions.burn_session(user_id)
```

### Управление квотами

```python
# Проверка возможности создания email
can_create, reason = await repo.can_user_create_email(user_id, daily_limit=10)

# Увеличение счетчика
await repo.counters.increment_daily_usage(user_id, 1)

# Получение оставшейся квоты
remaining = await repo.counters.get_remaining_quota(user_id, daily_limit=10)
```

## 🎯 Мониторинг писем (KashmailWatcherService)

### Фоновый сервис

```python
from workers.kashmail_watcher import get_watcher_service

# Получение сервиса
watcher = await get_watcher_service(database, bot_context)

# Добавление сессии мониторинга
await watcher.add_watch_session(
    user_id=123,
    jwt_token="jwt.token",
    address="test@example.com",
    chat_id=123,
    timeout_seconds=200
)

# Остановка мониторинга
await watcher.remove_watch_session(user_id)

# Получение статистики
active_count = watcher.get_active_sessions_count()
is_watching = watcher.is_user_watching(user_id)
```

### Алгоритм мониторинга
1. Поллинг GET /messages каждые 2-5 секунд
2. Прогрессивное увеличение интервала при отсутствии писем
3. Обработка rate limiting и ошибок
4. Автоматическая остановка по таймауту (200 сек)

## 🔍 Извлечение OTP кодов

### Поддерживаемые форматы

```python
from utils.otp_extract import extract_codes, extract_links

# Извлечение кодов
codes = extract_codes(content, subject)
# Поддерживает:
# - Цифровые коды: 123456, 4567
# - Буквенно-цифровые: ABC123, XY7Z89
# - С разделителями: 12-34, 56 78

# Извлечение ссылок
links = extract_links(html_content)
# Автоматическая очистка tracking параметров
```

### Алгоритм ранжирования кодов
1. **Релевантность по маркерам**: близость к словам "code", "verify", "otp"
2. **Оптимальная длина**: приоритет кодам 4-6 символов
3. **Позиция в тексте**: коды в начале текста имеют больший приоритет
4. **Фильтрация неподходящих**: исключение годов, простых последовательностей

## 🌍 Локализация

Поддерживаемые языки: **RU**, **UA**, **EN**

### Ключи локализации

```json
{
  "kashmail_menu_title": "📩 **KashMail - Временная почта**",
  "kashmail_generate_email": "📧 Сгенерировать временный email",
  "kashmail_wait_messages": "⏱ Ждать письмо (200 сек)",
  "kashmail_new_message": "Новое письмо в KashMail!",
  "kashmail_codes_found": "Найдены коды",
  // ... другие ключи
}
```

## 🧪 Тестирование

### Запуск юнит тестов

```bash
# Тесты извлечения OTP кодов
python -m pytest test_kashmail_otp_extract.py -v

# Интеграционные тесты с моками
python -m pytest test_kashmail_integration.py -v
```

### Покрытие тестами
- ✅ Извлечение OTP кодов и ссылок
- ✅ Mail.tm API с моками
- ✅ Репозиторий сессий
- ✅ Мониторинг писем
- ✅ Обработка ошибок и edge cases

## 🔒 Безопасность и приватность

### GDPR соответствие
- **Не сохраняем контент писем** - только метаданные
- **Автоматическое удаление**: истекшие сессии очищаются
- **Минимальное хранение**: только user_id, адрес, статус, timestamps

### Ограничения доступа
- **Дневные лимиты**: защита от злоупотребления
- **Одна активная сессия**: один адрес на пользователя
- **Таймауты**: автоматическое завершение сессий

## 📈 Мониторинг и логирование

### Логируемые события
```python
logger.info(f"Created KashMail session for user {user_id}: {address}")
logger.info(f"Got {len(messages)} messages")
logger.error(f"Failed to create temporary email: {e}")
```

### Метрики
- Количество созданных адресов
- Успешность получения писем
- Время ответа Mail.tm API
- Активные сессии мониторинга

## 🚨 Известные ограничения

1. **Зависимость от Mail.tm**: доступность сервиса влияет на функциональность
2. **Временность адресов**: адреса действуют 24 часа
3. **Rate limiting**: ограничения API Mail.tm (1 запрос/сек)
4. **Размер писем**: очень большие письма могут обрабатываться медленно

## 🛠️ Расширение функциональности

### Добавление новых провайдеров
Для добавления альтернативных провайдеров временной почты:

1. Реализуйте интерфейс `MailTmApi`
2. Добавьте конфигурацию провайдера
3. Обновите фабрику создания API клиентов

### Кастомизация извлечения кодов
Для добавления новых паттернов кодов в `utils/otp_extract.py`:

```python
# Добавьте новые регулярные выражения
patterns = [
    r'\b\d{4,8}\b',  # Существующий
    r'\bMY\d{6}\b',  # Новый паттерн
]

# Добавьте новые маркеры
code_markers = [
    'code', 'otp',   # Существующие
    'pin', 'token',  # Новые маркеры
]
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи бота для ошибок API
2. Убедитесь в корректности переменных окружения
3. Проверьте доступность Mail.tm API
4. Запустите тесты для диагностики

---

**KashMail v1.0** - Временная почта прямо в Telegram! 📩
