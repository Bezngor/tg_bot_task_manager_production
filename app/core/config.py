"""
Конфигурационный файл приложения
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
# Ищем .env файл в корне проекта (на 2 уровня выше)
env_path = Path(__file__).parent.parent.parent / '.env'
if not env_path.exists():
    # Если не найден, пробуем на 1 уровень выше (для совместимости)
    env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///task_manager.db')

# Encryption
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '')

# Flask API
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5050))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

# Roles
class Roles:
    ADMIN = 'admin'
    MANAGER = 'manager'  # Начальник
    EMPLOYEE = 'employee'  # Сотрудник

# Shifts
class Shifts:
    FIRST = 1  # 8:00 - 20:00
    SECOND = 2  # 20:00 - 8:00

SHIFT_TIMES = {
    Shifts.FIRST: {'start': '08:00', 'end': '20:00'},
    Shifts.SECOND: {'start': '20:00', 'end': '08:00'}
}
