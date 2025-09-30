# Keitaro Integration для KashHub Bot

## 📋 Описание

Модуль интеграции с Keitaro для получения моментальных уведомлений о конверсиях (регистрации, депозиты, отказы) прямо в Telegram.

## ✨ Возможности

- **S2S Postback** - моментальное получение событий из Keitaro
- **Гибкая маршрутизация** - настройка правил доставки по campaign_id, source и фильтрам
- **Антиспам защита** - rate limiting и дедупликация событий  
- **Мультиязычность** - поддержка RU/UA/EN
- **Безопасность** - уникальные секретные токены, без BOT_TOKEN в URL

## 🚀 Быстрый старт

### 1. Настройка окружения

Добавьте в `.env`:

```bash
# Обязательные
DATABASE_URL=postgresql://user:pass@localhost/dbname
WEBHOOK_DOMAIN=yourdomain.com  # Без https://

# Опциональные
KEITARO_WEBHOOK_PORT=8080  # Порт для webhook сервера
```

### 2. Запуск миграций

```bash
# Применение миграции для создания таблиц
alembic upgrade head
```

### 3. Настройка в боте

1. Откройте бота и выберите "💚 Keitaro уведомления"
2. Создайте профиль интеграции
3. Укажите чат для получения уведомлений
4. Скопируйте полученный Postback URL

### 4. Настройка в Keitaro

#### В кампании:
1. Перейдите в **Кампания → S2S Postback**
2. Добавьте новый Postback:
   - **URL**: вставьте URL из бота
   - **Метод**: POST
   - **Content-Type**: application/x-www-form-urlencoded

#### В источнике трафика:
1. Перейдите в **Источник → Postback URL**
2. Аналогично настройте URL и метод

#### Настройка полей (обязательно):

```
status={status}
transaction_id={transaction_id}
click_id={click_id}
campaign_id={campaign_id}
campaign_name={campaign_name}
offer_name={offer_name}
conversion_revenue={conversion_revenue}
payout={payout}
currency={currency}
country={country}
source={source}
creative_id={creative_id}
landing_name={landing_name}
sub_id_1={sub_id_1}
sub_id_2={sub_id_2}
```

## 📨 Примеры сообщений

### Регистрация
```
📝 Регистрация
Кампания: Campaign Name
Оффер: Offer Name
ГЕО: US
Sub1: utm_source
TX: abc123def456
```

### Депозит
```
💰 Депозит
Кампания: Campaign Name
Креатив: cr_123
Лендинг: Landing Page
Доход: 100 USD
Sub1: google | GEO: UK
TX: xyz789ghi012
```

### Отказ
```
⛔️ Отказ
Кампания: Campaign Name
Причина: invalid_geo
TX: qwe456rty789
```

## 🔀 Маршрутизация (расширенная)

### Создание правил

В боте можно настроить правила маршрутизации:

1. **По Campaign ID** - отправка событий определенной кампании в отдельный чат
2. **По Source** - группировка по источнику трафика
3. **Any** - универсальное правило

### Фильтры

- **Статусы** - только определенные типы событий (deposit, registration, rejected)
- **ГЕО** - фильтрация по странам

### Приоритет

Правила проверяются по приоритету (меньше число = выше приоритет).

## 🔧 Техническая архитектура

### Компоненты

1. **Web Server** (`web_server.py`) - aiohttp сервер для приема postback
2. **Handlers** (`features/keitaro/handlers.py`) - Telegram интерфейс настройки
3. **Templates** (`features/keitaro/templates.py`) - шаблоны сообщений
4. **Models** (`database/keitaro_models.py`) - SQLAlchemy модели

### База данных

#### Таблицы:
- `keitaro_profiles` - профили интеграции пользователей
- `keitaro_routes` - правила маршрутизации
- `keitaro_events` - лог событий для дедупликации

### Защита

- **Rate Limiting**: до 27 RPS на профиль
- **Дедупликация**: игнорирование повторных событий в течение TTL (по умолчанию 3600 сек)
- **Секретные токены**: уникальный токен для каждого профиля

## 🧪 Тестирование

### Запуск тестов

```bash
cd bot
python -m pytest tests/test_keitaro.py -v
```

### Тестовые сценарии

- ✅ Нормализация статусов
- ✅ Форматирование сумм
- ✅ Генерация сообщений
- ✅ Дедупликация событий
- ✅ Маршрутизация с фильтрами
- ✅ Rate limiting

### Ручное тестирование

1. В боте нажмите "🧪 Отправить тест"
2. Используйте curl для проверки webhook:

```bash
curl -X POST https://yourdomain.com:8080/integrations/keitaro/postback?secret=YOUR_SECRET \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "status=deposit&campaign_name=Test&conversion_revenue=100&currency=USD"
```

## 🚨 Мониторинг

### Логи

Все события логируются с уровнями:
- `INFO` - успешные события
- `WARNING` - rate limit, невалидные секреты
- `ERROR` - ошибки отправки сообщений

### Метрики в БД

```sql
-- Количество событий по профилю
SELECT profile_id, COUNT(*) as events_count 
FROM keitaro_events 
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY profile_id;

-- Ошибки доставки
SELECT * FROM keitaro_events 
WHERE processed = false AND error IS NOT NULL
ORDER BY created_at DESC LIMIT 10;
```

## 🔒 Безопасность

1. **Никогда не включайте BOT_TOKEN в Postback URL**
2. **Используйте HTTPS** для webhook домена
3. **Регулярно меняйте секреты** при подозрении на компрометацию
4. **Ограничивайте IP** на уровне nginx/CloudFlare (опционально)

## 🛠 Troubleshooting

### Не приходят уведомления

1. Проверьте статус профиля (включен/выключен)
2. Убедитесь что бот имеет доступ к указанному чату
3. Проверьте логи веб-сервера на порту 8080
4. Тестовое сообщение из бота работает?

### Ошибка "forbidden"

- Неверный secret в URL
- Профиль отключен
- Проверьте точное совпадение secret

### Rate limit exceeded

- Слишком много событий в секунду
- Увеличьте интервал отправки в Keitaro
- Или измените rate_limit_rps в БД

### Дубликаты событий

- Увеличьте dedup_ttl_sec в профиле
- Проверьте уникальность transaction_id в Keitaro

## 📝 Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `WEBHOOK_DOMAIN` | Домен для webhook URL | YOUR_DOMAIN.COM |
| `KEITARO_WEBHOOK_PORT` | Порт веб-сервера | 8080 |
| `DATABASE_URL` | PostgreSQL connection | - |

## 🤝 Поддержка

При проблемах с интеграцией обращайтесь в поддержку бота с указанием:
- Скриншот настроек Keitaro
- Postback URL
- Примерное время события
- Chat ID куда должны приходить уведомления
