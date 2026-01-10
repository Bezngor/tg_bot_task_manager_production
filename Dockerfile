# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем необходимые директории
RUN mkdir -p logs reports

# Устанавливаем переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///task_manager.db

# Открываем порт для API (если нужно)
EXPOSE 5050

# Команда по умолчанию - запуск бота
# Для запуска API используйте: python -m app.api.api
# Для запуска админ-панели используйте: python -m app.admin.admin_panel
CMD ["python", "-m", "app.bot.bot"]
