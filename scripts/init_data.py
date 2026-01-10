"""
Скрипт для инициализации базы данных и создания тестовых данных
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_db, init_sample_data

if __name__ == '__main__':
    print("Инициализация базы данных...")
    init_db()
    
    print("Создание тестовых данных...")
    init_sample_data()
    
    print("Готово! База данных инициализирована с тестовыми данными.")
