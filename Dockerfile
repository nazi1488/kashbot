# Multi-stage build для оптимизации размера
FROM python:3.11-slim as builder

# Установка зависимостей для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements_prod.txt /tmp/
RUN pip install --user --no-cache-dir -r /tmp/requirements_prod.txt

# Production образ
FROM python:3.11-slim

# Метаданные
LABEL maintainer="your-email@example.com"
LABEL version="1.0"
LABEL description="Telegram Bot with Celery Workers"

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app /tmp/bot_temp && \
    chown -R botuser:botuser /app /tmp/bot_temp

# Копируем Python пакеты из builder
COPY --from=builder /root/.local /home/botuser/.local

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем код приложения
COPY --chown=botuser:botuser . .

# Переключаемся на пользователя
USER botuser

# Добавляем пути
ENV PATH=/home/botuser/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Временная директория для обработки файлов
ENV TEMP_DIR=/tmp/bot_temp

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8443/health || exit 1

# По умолчанию запускаем бота
CMD ["python", "main.py"]
