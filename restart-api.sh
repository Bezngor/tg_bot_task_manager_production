#!/bin/bash

# Скрипт для перезапуска API сервера с переменными из .env файла

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
CONTAINER_NAME="tg_bot_task_manager_api"
IMAGE="ghcr.io/bezngor/tg_bot_task_manager_production:main"

if [ ! -f "$ENV_FILE" ]; then
    echo "Ошибка: файл .env не найден в $ENV_FILE"
    exit 1
fi

echo "Остановка и удаление существующего API контейнера..."
docker stop "$CONTAINER_NAME" 2>/dev/null
docker rm "$CONTAINER_NAME" 2>/dev/null

echo "Загрузка переменных из .env..."
# Загружаем переменные из .env файла
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)

echo "Запуск нового API контейнера с переменными из .env..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e DATABASE_URL="${DATABASE_URL:-sqlite:///task_manager.db}" \
    -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
    -e FLASK_HOST="${FLASK_HOST:-0.0.0.0}" \
    -e FLASK_PORT="${FLASK_PORT:-5050}" \
    -e FLASK_DEBUG="${FLASK_DEBUG:-False}" \
    -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
    -e LOG_FILE="${LOG_FILE:-api.log}" \
    -p 5050:5050 \
    -v "$SCRIPT_DIR/task_manager.db:/app/task_manager.db" \
    -v "$SCRIPT_DIR/data:/app/data" \
    -v "$SCRIPT_DIR/logs:/app/logs" \
    -v "$SCRIPT_DIR/reports:/app/reports" \
    "$IMAGE" \
    python api.py

if [ $? -eq 0 ]; then
    echo "API контейнер успешно запущен!"
    echo "Проверка статуса..."
    sleep 2
    docker ps | grep "$CONTAINER_NAME"
    echo ""
    echo "Последние логи:"
    docker logs "$CONTAINER_NAME" --tail 5
    echo ""
    echo "Проверка API..."
    sleep 2
    curl -s "http://localhost:5050/users?role=employee" | python3 -m json.tool 2>/dev/null | head -10 || echo "API еще запускается..."
else
    echo "Ошибка при запуске контейнера"
    exit 1
fi
