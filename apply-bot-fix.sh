#!/bin/bash
# Скрипт для применения исправлений к bot.py в контейнере

CONTAINER_NAME="tg_bot_task_manager"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Контейнер $CONTAINER_NAME не запущен"
    exit 1
fi

echo "Применение исправлений к bot.py..."

# Исправление 1: сделать execute асинхронным
docker exec "$CONTAINER_NAME" sed -i 's/    def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):/    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):/' /app/bot.py

# Исправление 2: добавить await для reply_text в StartCommand
docker exec "$CONTAINER_NAME" sed -i '57s/^        update\.message\.reply_text/        await update.message.reply_text/' /app/bot.py

# Исправление 3: добавить await при вызове command.execute
docker exec "$CONTAINER_NAME" sed -i 's/    command\.execute(update, context)/    await command.execute(update, context)/' /app/bot.py

echo "Исправления применены успешно"
