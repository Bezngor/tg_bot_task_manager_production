#!/bin/bash

# Скрипт для запуска админ-панели в Docker контейнере

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="task_manager_admin"
IMAGE="ghcr.io/bezngor/tg_bot_task_manager_production:main"

echo "Остановка существующего контейнера админ-панели..."
docker stop "$CONTAINER_NAME" 2>/dev/null
docker rm "$CONTAINER_NAME" 2>/dev/null

# Проверяем наличие .env файла
ENV_FILE="$SCRIPT_DIR/.env"
ENV_FILE_OPTION=""
if [ -f "$ENV_FILE" ]; then
    ENV_FILE_OPTION="--env-file $ENV_FILE"
fi

echo "Запуск админ-панели..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p 5051:5051 \
    $ENV_FILE_OPTION \
    -v "$SCRIPT_DIR/task_manager.db:/app/task_manager.db" \
    -v "$SCRIPT_DIR/data:/app/data" \
    -v "$SCRIPT_DIR/logs:/app/logs" \
    -v "$SCRIPT_DIR/reports:/app/reports" \
    "$IMAGE" \
    python -m app.admin.admin_panel

if [ $? -eq 0 ]; then
    echo "Админ-панель запущена!"
    # Определяем IP хоста
    if command -v hostname >/dev/null 2>&1; then
        HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")
    else
        HOST_IP="localhost"
    fi
    echo "Доступна по адресу: http://$HOST_IP:5051"
    echo "Или локально: http://localhost:5051"
    echo "На продакшн сервере: http://155.212.184.11:5051"
    sleep 2
    docker logs "$CONTAINER_NAME" --tail 10
else
    echo "Ошибка при запуске"
    exit 1
fi
