# Redis Setup для Random Face Generator

Redis требуется для работы модуля Random Face Generator (квотирование и антиспам).

## 🚀 Быстрый запуск через Docker

### Вариант 1: Docker Compose (рекомендуется)

```bash
# Запуск Redis
docker-compose -f docker-compose.redis.yml up -d

# Проверка статуса
docker-compose -f docker-compose.redis.yml ps

# Остановка Redis
docker-compose -f docker-compose.redis.yml down
```

### Вариант 2: Прямой Docker

```bash
# Запуск Redis
docker run --name kashhub-redis -d -p 6379:6379 redis:7-alpine

# Проверка статуса
docker ps | grep redis

# Остановка Redis
docker stop kashhub-redis
docker rm kashhub-redis
```

## 🔧 Установка Redis локально

### macOS (Homebrew)
```bash
brew install redis
brew services start redis
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Windows
Скачайте Redis с официального сайта или используйте WSL с Ubuntu инструкциями.

## ✅ Проверка подключения

```bash
# Через redis-cli (если установлен локально)
redis-cli ping

# Через Python
python3 -c "
import redis.asyncio as redis
import asyncio

async def test():
    r = redis.from_url('redis://localhost:6379/0')
    await r.ping()
    print('✅ Redis работает!')
    await r.aclose()

asyncio.run(test())
"
```

## ⚙️ Конфигурация в .env

```bash
# Настройки Random Face Generator
REDIS_URL=redis://localhost:6379/0
FACE_QUOTA_PER_DAY=10
```

## 🔒 Продакшен настройки

Для продакшена рекомендуется:

1. **Настроить пароль для Redis:**
```bash
# В redis.conf
requirepass your_secure_password
```

2. **Обновить REDIS_URL:**
```bash
REDIS_URL=redis://:password@localhost:6379/0
```

3. **Настроить персистентность:**
```bash
# В redis.conf
save 900 1
save 300 10
save 60 10000
```

## 🚨 Graceful Degradation

Если Redis недоступен:
- Модуль Random Face автоматически отключается
- Бот продолжает работать без генерации лиц
- В логах будет предупреждение: "Random Face will not be available"

## 📊 Мониторинг

### Проверка использования памяти
```bash
redis-cli info memory
```

### Мониторинг команд
```bash
redis-cli monitor
```

### Просмотр ключей Random Face
```bash
redis-cli keys "face:*"
```

## 🛠 Troubleshooting

### Ошибка подключения
```
Failed to connect to Redis: [Errno 61] Connection refused
```

**Решение:**
1. Проверьте, что Redis запущен: `docker ps | grep redis`
2. Проверьте порт: `netstat -an | grep 6379`
3. Проверьте REDIS_URL в .env

### Ошибка аутентификации
```
AuthenticationError: Authentication required
```

**Решение:**
Добавьте пароль в REDIS_URL: `redis://:password@localhost:6379/0`

### Проблемы с производительностью
1. Увеличьте `maxmemory` в redis.conf
2. Настройте `maxmemory-policy allkeys-lru`
3. Мониторьте `redis-cli info stats`
