#!/bin/bash

# Скрипт установки self-hosted Telegram Bot API для VPS
# Протестировано на Ubuntu 20.04/22.04

set -e

echo "================================================"
echo "Установка self-hosted Telegram Bot API"
echo "================================================"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
   echo "Запустите скрипт с правами root: sudo $0" 
   exit 1
fi

# Обновление пакетов
echo "Обновление системы..."
apt-get update
apt-get upgrade -y

# Установка Docker если не установлен
if ! command -v docker &> /dev/null; then
    echo "Установка Docker..."
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
fi

# Установка Docker Compose если не установлен
if ! command -v docker-compose &> /dev/null; then
    echo "Установка Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Создание директории для проекта
INSTALL_DIR="/opt/telegram-bot-api"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Запрос учетных данных
echo ""
echo "Для работы self-hosted Bot API требуются учетные данные Telegram API."
echo "Получить их можно на https://my.telegram.org/apps"
echo ""
read -p "Введите TELEGRAM_API_ID: " API_ID
read -p "Введите TELEGRAM_API_HASH: " API_HASH

# Создание .env файла
cat > $INSTALL_DIR/.env <<EOF
TELEGRAM_API_ID=$API_ID
TELEGRAM_API_HASH=$API_HASH
EOF

# Создание docker-compose.yml
cat > $INSTALL_DIR/docker-compose.yml <<'EOF'
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
      - "--stat-port=8082"
      - "--max-file-upload-size=2000"
      - "--file-gc-timeout=3600"
      - "--dir=/var/lib/telegram-bot-api"
      - "--log=/var/log/telegram-bot-api/telegram-bot-api.log"
      - "--verbosity=2"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  telegram-bot-api-data:
    driver: local
EOF

# Создание директорий для данных
mkdir -p $INSTALL_DIR/telegram-bot-api-data
mkdir -p $INSTALL_DIR/logs

# Запуск контейнера
echo "Запуск Telegram Bot API..."
docker-compose up -d

# Создание systemd сервиса для автозапуска
cat > /etc/systemd/system/telegram-bot-api.service <<EOF
[Unit]
Description=Telegram Bot API
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart

[Install]
WantedBy=multi-user.target
EOF

# Активация сервиса
systemctl daemon-reload
systemctl enable telegram-bot-api
systemctl start telegram-bot-api

# Настройка firewall
if command -v ufw &> /dev/null; then
    echo "Настройка firewall..."
    ufw allow 8081/tcp
    ufw allow 8082/tcp
fi

# Проверка статуса
sleep 5
if docker ps | grep -q telegram-bot-api; then
    echo ""
    echo "================================================"
    echo "✅ Telegram Bot API успешно установлен!"
    echo "================================================"
    echo ""
    echo "API доступен по адресу: http://$(hostname -I | cut -d' ' -f1):8081"
    echo ""
    echo "Для использования в боте добавьте в .env:"
    echo "USE_LOCAL_BOT_API=true"
    echo "LOCAL_BOT_API_URL=http://$(hostname -I | cut -d' ' -f1):8081"
    echo ""
    echo "Команды управления:"
    echo "  Просмотр логов: docker logs telegram-bot-api"
    echo "  Перезапуск: docker-compose restart"
    echo "  Остановка: docker-compose down"
    echo ""
else
    echo "❌ Ошибка запуска Telegram Bot API"
    echo "Проверьте логи: docker logs telegram-bot-api"
    exit 1
fi
