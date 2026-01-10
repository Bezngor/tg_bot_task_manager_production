#!/bin/bash

# Скрипт для перезапуска Telegram бота с переменными из .env файла

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
CONTAINER_NAME="tg_bot_task_manager"
IMAGE="ghcr.io/bezngor/tg_bot_task_manager_production:main"

if [ ! -f "$ENV_FILE" ]; then
    echo "Ошибка: файл .env не найден в $ENV_FILE"
    exit 1
fi

echo "Остановка и удаление существующего контейнера..."
docker stop "$CONTAINER_NAME" 2>/dev/null
docker rm "$CONTAINER_NAME" 2>/dev/null

echo "Загрузка переменных из .env..."
# Загружаем переменные из .env файла
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)

echo "Запуск нового контейнера с переменными из .env..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e DATABASE_URL="${DATABASE_URL:-sqlite:///task_manager.db}" \
    -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
    -e FLASK_HOST="${FLASK_HOST:-0.0.0.0}" \
    -e FLASK_PORT="${FLASK_PORT:-5000}" \
    -e FLASK_DEBUG="${FLASK_DEBUG:-False}" \
    -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
    -e LOG_FILE="${LOG_FILE:-bot.log}" \
    -v "$SCRIPT_DIR/task_manager.db:/app/task_manager.db" \
    -v "$SCRIPT_DIR/data:/app/data" \
    -v "$SCRIPT_DIR/logs:/app/logs" \
    -v "$SCRIPT_DIR/reports:/app/reports" \
    "$IMAGE" \
    python bot.py

# Применяем исправления к bot.py
echo "Применение исправлений к bot.py..."
sleep 3
"$SCRIPT_DIR/apply-bot-fix.sh"
sleep 2
docker restart "$CONTAINER_NAME"

if [ $? -eq 0 ]; then
    echo "Контейнер успешно запущен!"
    echo "Проверка статуса..."
    sleep 2
    docker ps | grep "$CONTAINER_NAME"
    echo ""
    echo "Последние логи:"
    docker logs "$CONTAINER_NAME" --tail 5
else
    echo "Ошибка при запуске контейнера"
    exit 1
fi
