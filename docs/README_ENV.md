# Настройка переменных окружения для Telegram бота

## Проблема

Если контейнер запускается с жестко заданными переменными окружения из образа Docker, он будет использовать значения по умолчанию (например, `your_telegram_bot_token_here`) вместо значений из `.env` файла.

## Решение

### Автоматический способ (рекомендуется)

Используйте скрипт `restart-bot.sh`:

```bash
cd /opt/task_manager
./restart-bot.sh
```

Этот скрипт:
1. Остановит и удалит существующий контейнер
2. Загрузит переменные из `.env` файла
3. Запустит новый контейнер с правильными переменными

### Ручной способ

Если нужно перезапустить контейнер вручную:

```bash
cd /opt/task_manager

# Остановить и удалить контейнер
docker stop tg_bot_task_manager
docker rm tg_bot_task_manager

# Загрузить переменные и запустить
source .env
docker run -d \
    --name tg_bot_task_manager \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e DATABASE_URL="$DATABASE_URL" \
    -e ENCRYPTION_KEY="$ENCRYPTION_KEY" \
    -e FLASK_HOST="$FLASK_HOST" \
    -e FLASK_PORT="$FLASK_PORT" \
    -e FLASK_DEBUG="$FLASK_DEBUG" \
    -e LOG_LEVEL="$LOG_LEVEL" \
    -e LOG_FILE="$LOG_FILE" \
    -v /opt/task_manager/task_manager.db:/app/task_manager.db \
    -v /opt/task_manager/data:/app/data \
    -v /opt/task_manager/logs:/app/logs \
    -v /opt/task_manager/reports:/app/reports \
    ghcr.io/bezngor/tg_bot_task_manager_production:main \
    python bot.py
```

## Проверка

Проверить, что токен установлен правильно:

```bash
docker inspect tg_bot_task_manager --format '{{range .Config.Env}}{{if eq (index (split . "=") 0) "TELEGRAM_BOT_TOKEN"}}{{.}}{{end}}{{end}}'
```

Проверить логи бота:

```bash
docker logs tg_bot_task_manager --tail 20
```

Если все правильно, в логах должно быть:
- `HTTP/1.1 200 OK` при запросах к Telegram API
- `Application started` без ошибок InvalidToken

## Важно

⚠️ **Всегда используйте переменные окружения при запуске Docker контейнера**, если в образе есть значения по умолчанию. Просто наличие `.env` файла на хосте не означает, что контейнер его автоматически прочитает.
