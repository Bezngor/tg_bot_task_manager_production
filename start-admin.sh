#!/bin/bash

# Скрипт для запуска админ-панели в Docker контейнере

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="task_manager_admin"
IMAGE="ghcr.io/bezngor/tg_bot_task_manager_production:main"

echo "Остановка существующего контейнера админ-панели..."
docker stop "$CONTAINER_NAME" 2>/dev/null
docker rm "$CONTAINER_NAME" 2>/dev/null

echo "Запуск админ-панели..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p 5051:5051 \
    -v "$SCRIPT_DIR/admin_panel.py:/app/admin_panel.py" \
    -v "$SCRIPT_DIR/task_manager.db:/app/task_manager.db" \
    -v "$SCRIPT_DIR/data:/app/data" \
    -v "$SCRIPT_DIR/logs:/app/logs" \
    -v "$SCRIPT_DIR/reports:/app/reports" \
    -e DATABASE_URL="sqlite:///task_manager.db" \
    "$IMAGE" \
    python admin_panel.py

if [ $? -eq 0 ]; then
    echo "Админ-панель запущена!"
    echo "Доступна по адресу: http://$(hostname -I | awk '{print $1}'):5051"
    echo "Или локально: http://localhost:5051"
    sleep 2
    docker logs "$CONTAINER_NAME" --tail 10
else
    echo "Ошибка при запуске"
    exit 1
fi
