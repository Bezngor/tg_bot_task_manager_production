#!/bin/bash

# Скрипт для перезапуска всех сервисов (бот + API)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Перезапуск всех сервисов ==="
echo ""

echo "1. Перезапуск Telegram бота..."
"$SCRIPT_DIR/restart-bot.sh"
echo ""

echo "2. Перезапуск API сервера..."
"$SCRIPT_DIR/restart-api.sh"
echo ""

echo "=== Все сервисы перезапущены ==="
echo ""
echo "Статус контейнеров:"
docker ps | grep tg_bot_task_manager
