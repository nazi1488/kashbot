# 🚀 Self-hosted Telegram Bot API Setup Guide

## 📋 Преимущества Self-hosted Bot API

1. **Поддержка больших файлов**: до 2GB (вместо 20MB в обычном API)
2. **Высокая скорость**: прямая связь между ботом и API
3. **Полный контроль**: данные не проходят через сервера Telegram
4. **Кастомизация**: настройка лимитов и параметров

## 🛠️ Установка на VPS

### Требования
- Ubuntu 20.04/22.04 или Debian 10/11
- Минимум 2GB RAM
- 20GB свободного места на диске
- Docker и Docker Compose

### Быстрая установка

```bash
# Скачайте скрипт установки
wget https://raw.githubusercontent.com/your-repo/bot/main/install_telegram_bot_api.sh

# Запустите установку
sudo bash install_telegram_bot_api.sh
```

### Ручная установка

1. **Получите API credentials**
   - Перейдите на https://my.telegram.org/apps
   - Создайте приложение
   - Скопируйте API ID и API Hash

2. **Установите Docker**
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

3. **Создайте конфигурацию**
```bash
sudo mkdir -p /opt/telegram-bot-api
cd /opt/telegram-bot-api
```

4. **Создайте файл `.env`**
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

5. **Создайте `docker-compose.yml`**
```yaml
version: '3.8'

services:
  telegram-bot-api:
    image: aiogram/telegram-bot-api:latest
    container_name: telegram-bot-api
    restart: unless-stopped
    environment:
      TELEGRAM_API_ID: "${TELEGRAM_API_ID}"
      TELEGRAM_API_HASH: "${TELEGRAM_API_HASH}"
      TELEGRAM_LOCAL: "true"
    ports:
      - "8081:8081"
    volumes:
      - ./telegram-bot-api-data:/var/lib/telegram-bot-api
      - ./logs:/var/log/telegram-bot-api
    command:
      - "--api-id=${TELEGRAM_API_ID}"
      - "--api-hash=${TELEGRAM_API_HASH}"
      - "--local"
      - "--port=8081"
      - "--max-file-upload-size=2000"
      - "--file-gc-timeout=3600"
```

6. **Запустите сервис**
```bash
sudo docker-compose up -d
```

## ⚙️ Настройка бота

### 1. Обновите `.env.production`

```env
# Self-hosted Bot API
USE_LOCAL_BOT_API=true
LOCAL_BOT_API_URL=http://YOUR_VPS_IP:8081

# Limits (500MB для пользователей)
MAX_FILE_SIZE=524288000
```

### 2. Проверьте конфигурацию

```bash
# Проверьте статус API
curl http://YOUR_VPS_IP:8081/health

# Проверьте логи
docker logs telegram-bot-api
```

### 3. Запустите бота

```bash
python3 main.py
```

## 🔧 Настройка firewall

```bash
# Откройте порты
sudo ufw allow 8081/tcp  # Bot API
sudo ufw allow 8443/tcp  # Webhook (если используется)
```

## 🌟 Новые возможности

### Изменения в уникализаторе

1. **Новый порядок запросов**:
   - Сначала запрашивается файл
   - Затем количество копий
   - Более логичный UX

2. **Поддержка больших файлов**:
   - До 500MB для пользователей
   - Автоматическая обработка без ошибок
   - Быстрое скачивание и обработка

3. **Улучшенная производительность**:
   - Прямая связь с API
   - Нет задержек от прокси Telegram
   - Параллельная обработка

## 📊 Мониторинг

### Просмотр статистики
```bash
# Статус контейнера
docker ps | grep telegram-bot-api

# Использование ресурсов
docker stats telegram-bot-api

# Просмотр логов
docker logs -f telegram-bot-api --tail 100
```

### Автоматический перезапуск
```bash
# Создайте systemd сервис
sudo cat > /etc/systemd/system/telegram-bot-api.service <<EOF
[Unit]
Description=Telegram Bot API
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/telegram-bot-api
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
ExecReload=/usr/bin/docker-compose restart

[Install]
WantedBy=multi-user.target
EOF

# Активируйте сервис
sudo systemctl enable telegram-bot-api
sudo systemctl start telegram-bot-api
```

## 🚨 Решение проблем

### API не запускается
```bash
# Проверьте логи
docker logs telegram-bot-api

# Проверьте порты
sudo netstat -tulpn | grep 8081

# Перезапустите
docker-compose restart
```

### Бот не подключается к API
1. Проверьте firewall
2. Проверьте URL в .env.production
3. Убедитесь что USE_LOCAL_BOT_API=true

### Ошибки с большими файлами
1. Проверьте свободное место на диске
2. Увеличьте лимиты Docker:
```bash
docker-compose down
# Отредактируйте docker-compose.yml
# Добавьте: --max-file-upload-size=2000
docker-compose up -d
```

## 📈 Производительность

### Рекомендуемые параметры VPS
- **Минимум**: 2 vCPU, 2GB RAM, 20GB SSD
- **Оптимально**: 4 vCPU, 4GB RAM, 50GB SSD
- **Для больших нагрузок**: 8 vCPU, 8GB RAM, 100GB SSD

### Оптимизация
```yaml
# В docker-compose.yml добавьте лимиты
services:
  telegram-bot-api:
    # ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## ✅ Проверка работы

### Тестирование
```bash
# Запустите тесты
python3 test_self_hosted_api.py
```

### Ожидаемый результат
```
🚀 ТЕСТИРОВАНИЕ SELF-HOSTED TELEGRAM BOT API
============================================================
✅ Конфигурация загружена корректно
✅ Новый поток работает
✅ Большой файл обработан
✅ Обработка количества копий
✅ Скачивание большого файла

📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:
✅ Пройдено: 5/5
🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!
```

## 📝 Заключение

С self-hosted Telegram Bot API ваш бот может:
- ✅ Обрабатывать файлы до 500MB
- ✅ Работать быстрее и стабильнее
- ✅ Не зависеть от ограничений Telegram
- ✅ Масштабироваться под нагрузку

**Готово к production!** 🚀
