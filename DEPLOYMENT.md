# 🚀 Руководство по развертыванию Production-ready бота

## 📋 Требования к VPS

- **OS**: Ubuntu 20.04/22.04 LTS
- **CPU**: минимум 2 ядра (рекомендуется 4)
- **RAM**: минимум 4GB (рекомендуется 8GB)
- **Disk**: 50GB SSD
- **Network**: публичный IP, открытые порты 80, 443

## 🛠 Пошаговая установка

### 1. Подготовка сервера

```bash
# Подключаемся к серверу
ssh root@your-server-ip

# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем базовые пакеты
apt install -y curl git vim htop fail2ban ufw

# Настраиваем firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### 2. Установка Docker и Docker Compose

```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 3. Клонирование проекта

```bash
# Создаем директорию
mkdir -p /opt/telegram-bot
cd /opt/telegram-bot

# Клонируем репозиторий (замените на ваш)
git clone https://github.com/yourusername/telegram-bot.git .

# Даем права на выполнение скрипту
chmod +x deploy.sh
```

### 4. Настройка окружения

```bash
# Копируем production конфиг
cp .env.production .env

# Редактируем конфигурацию
vim .env
```

**Обязательно измените:**
- `BOT_TOKEN` - токен вашего бота
- `DB_PASSWORD` - пароль базы данных
- `WEBHOOK_DOMAIN` - ваш домен
- `FLOWER_PASSWORD` - пароль для мониторинга

### 5. SSL сертификат

```bash
# Устанавливаем certbot
apt install -y certbot python3-certbot-nginx

# Получаем сертификат
certbot certonly --standalone -d your-domain.com

# Создаем символические ссылки
mkdir -p /opt/telegram-bot/ssl
ln -s /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/telegram-bot/ssl/
ln -s /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/telegram-bot/ssl/
```

### 6. Запуск приложения

```bash
cd /opt/telegram-bot

# Сборка образов
docker-compose build

# Запуск базы данных и Redis
docker-compose up -d postgres redis

# Ждем инициализации
sleep 10

# Применяем миграции
docker-compose run --rm bot alembic upgrade head

# Запускаем все сервисы
docker-compose up -d

# Проверяем статус
docker-compose ps
```

### 7. Настройка Nginx

```bash
# Копируем конфиг
cp nginx.conf /etc/nginx/sites-available/telegram-bot

# Заменяем домен
sed -i 's/your-domain.com/YOUR_ACTUAL_DOMAIN/g' /etc/nginx/sites-available/telegram-bot

# Активируем сайт
ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Проверяем конфигурацию
nginx -t

# Перезапускаем Nginx
systemctl restart nginx
```

## 📊 Мониторинг

### Flower (Celery мониторинг)
```
https://your-domain.com/flower/
Login: admin
Password: [из .env]
```

### Логи
```bash
# Все логи
docker-compose logs -f

# Логи бота
docker-compose logs -f bot

# Логи воркеров
docker-compose logs -f worker_video worker_image

# Системные метрики
docker stats
```

### Health check
```bash
curl https://your-domain.com/health
```

## 🔧 Обслуживание

### Обновление кода
```bash
cd /opt/telegram-bot
./deploy.sh update
```

### Бэкап
```bash
./deploy.sh backup
```

### Перезапуск
```bash
./deploy.sh restart
```

### Остановка
```bash
./deploy.sh stop
```

## 📈 Нагрузочное тестирование

```bash
# Установка Locust
pip install locust faker

# Запуск теста (с другой машины)
locust -f load_test.py --host=https://your-domain.com \
       --users=50 --spawn-rate=2 --run-time=5m

# Или через веб-интерфейс
locust -f load_test.py --host=https://your-domain.com
# Открыть http://localhost:8089
```

### Ожидаемые метрики:
- **50 пользователей**: < 500ms response time
- **100 пользователей**: < 1s response time  
- **200 пользователей**: < 2s response time

## 🚨 Troubleshooting

### Бот не отвечает
```bash
# Проверяем webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Проверяем контейнеры
docker-compose ps
docker-compose logs bot --tail=100
```

### Высокая нагрузка CPU
```bash
# Проверяем процессы
docker stats

# Проверяем зомби FFmpeg
ps aux | grep ffmpeg

# Принудительная очистка
docker-compose exec worker_video pkill -9 ffmpeg
```

### База данных недоступна
```bash
# Проверяем подключение
docker-compose exec postgres psql -U bot_user -d bot_db -c "SELECT 1"

# Перезапуск
docker-compose restart postgres
```

### Очередь переполнена
```bash
# Проверяем Redis
docker-compose exec redis redis-cli
> LLEN celery
> FLUSHDB  # Осторожно! Очищает всё

# Масштабирование воркеров
docker-compose up -d --scale worker_video=3
```

## 🔐 Безопасность

1. **Регулярные обновления**
```bash
apt update && apt upgrade -y
docker-compose pull
docker-compose up -d
```

2. **Мониторинг логов**
```bash
tail -f /var/log/nginx/access.log
fail2ban-client status
```

3. **Ротация секретов**
- Меняйте webhook secret каждые 3 месяца
- Обновляйте пароли БД каждые 6 месяцев
- Используйте разные пароли для всех сервисов

4. **Бэкапы**
```bash
# Автоматический бэкап каждую ночь
crontab -e
0 3 * * * /opt/telegram-bot/deploy.sh backup
```

## 📞 Поддержка

- **Документация**: [Python Telegram Bot](https://python-telegram-bot.org/)
- **Celery**: [docs.celeryproject.org](https://docs.celeryproject.org/)
- **Docker**: [docs.docker.com](https://docs.docker.com/)

---

**Последнее обновление**: 2024-01
