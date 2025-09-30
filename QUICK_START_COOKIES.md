# 🚀 Быстрый старт системы Cookies

## 📋 Шаг 1: Применить миграции базы данных

```bash
# Применить миграции
python apply_migrations.py --apply

# Или через alembic напрямую
alembic upgrade head
```

## 🧪 Шаг 2: Протестировать систему

```bash
# Запустить тесты
python test_cookies_system.py
```

Вы должны увидеть:
```
✅ Fingerprint Generator: PASSED
✅ Cookies Manager: PASSED
✅ Video Downloader: PASSED
✅ Full Integration: PASSED
```

## 🍪 Шаг 3: Добавить cookies через админ панель

### Вариант А: Через бота

1. Запустите бота: `python main.py`
2. Отправьте команду: `/admin`
3. Выберите: `🍪 Управление Cookies`
4. Нажмите на платформу: `➕ Instagram`
5. Отправьте cookies в формате JSON

### Вариант Б: Через скрипт

```python
import asyncio
from database import Database
from utils.cookies_manager import CookiesManager
import config

async def add_cookies():
    db = Database(config.DATABASE_URL)
    manager = CookiesManager(db)
    
    # Ваши cookies в формате JSON
    cookies = """[
        {"domain":".instagram.com","name":"sessionid","value":"..."},
        {"domain":".instagram.com","name":"csrftoken","value":"..."}
    ]"""
    
    success = await manager.add_cookies(
        platform="instagram",
        cookies_data=cookies,
        notes="My Instagram account"
    )
    
    print("✅ Cookies added!" if success else "❌ Failed")

asyncio.run(add_cookies())
```

## 📥 Шаг 4: Получить cookies из браузера

### Chrome/Edge с расширением EditThisCookie:

1. Установите расширение [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
2. Откройте Instagram/TikTok/YouTube и войдите
3. Нажмите на иконку расширения
4. Нажмите экспорт (📤) → Format: JSON
5. Скопируйте результат

### Firefox с расширением cookies.txt:

1. Установите [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Откройте нужный сайт и войдите
3. Нажмите на расширение → Export
4. Скопируйте результат

## ✅ Шаг 5: Проверить работу

Отправьте боту ссылку на видео:
- Instagram: `https://www.instagram.com/reel/C1234567890/`
- TikTok: `https://www.tiktok.com/@username/video/7123456789`
- YouTube Shorts: `https://www.youtube.com/shorts/abc123DEF456`

## 📊 Мониторинг

### Просмотр статистики:
```bash
# В админ панели бота
/admin → 🍪 Управление Cookies
```

### Просмотр логов:
```bash
# Все операции с cookies
tail -f bot.log | grep -i cookies

# Успешные скачивания
tail -f bot.log | grep "Successfully downloaded"

# Ошибки
tail -f bot.log | grep -i error
```

### Проверка БД:
```sql
-- Активные cookies
SELECT platform, COUNT(*) as count 
FROM platform_cookies 
WHERE is_active = true 
GROUP BY platform;

-- Последние скачивания
SELECT * FROM download_logs 
ORDER BY created_at DESC 
LIMIT 10;
```

## ⚠️ Частые проблемы и решения

### "No cookies found"
```bash
# Проверьте, что cookies добавлены
psql $DATABASE_URL -c "SELECT * FROM platform_cookies;"
```

### "Video is private"
- Cookies истекли или от аккаунта без доступа
- Добавьте новые cookies от аккаунта с доступом

### "Too many requests"
- Добавьте больше cookies для ротации
- Подождите несколько минут

## 🎯 Проверочный чек-лист

- [ ] База данных настроена (`DATABASE_URL` в `.env`)
- [ ] Миграции применены (`alembic upgrade head`)
- [ ] Тесты проходят (`python test_cookies_system.py`)
- [ ] Cookies добавлены через админ панель
- [ ] Бот скачивает видео успешно

## 💡 Советы

1. **Используйте разные аккаунты** для разных cookies
2. **Обновляйте cookies** каждые 7-14 дней
3. **Держите минимум 3 cookies** на платформу
4. **Мониторьте статистику** через админ панель
5. **Проверяйте логи** при проблемах

## 📞 Поддержка

При проблемах проверьте:
1. Логи: `tail -f bot.log`
2. Статус БД: `psql $DATABASE_URL`
3. Cookies статус в админ панели
4. Документацию: `COOKIES_SYSTEM_README.md`
