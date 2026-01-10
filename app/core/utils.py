"""
Вспомогательные утилиты
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd
from .config import ENCRYPTION_KEY

# Настройка логирования
def setup_logging(log_file='bot.log', log_level=logging.INFO):
    """Настройка системы логирования"""
    # Ищем папку logs в корне проекта (на 2 уровня выше от app/core)
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_path = log_dir / log_file
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()


class DataEncryptor:
    """Класс для шифрования/дешифрования данных согласно ФЗ-152"""
    
    def __init__(self, key=None):
        """
        Инициализация шифровальщика
        
        Args:
            key: ключ шифрования (32 байта в base64). Если None, используется из конфига
        """
        if key is None:
            key = ENCRYPTION_KEY.encode() if ENCRYPTION_KEY else None
        
        if key is None or len(key) < 32:
            raise ValueError("Encryption key must be at least 32 bytes")
        
        # Fernet требует ключ длиной 32 байта в base64
        if isinstance(key, str):
            key = key.encode()
        
        # Если ключ не в формате base64, преобразуем его
        try:
            self.cipher = Fernet(key)
        except Exception:
            # Генерируем ключ из переданной строки
            import hashlib
            key_hash = hashlib.sha256(key).digest()
            from base64 import urlsafe_b64encode
            key_b64 = urlsafe_b64encode(key_hash)
            self.cipher = Fernet(key_b64)
    
    def encrypt(self, data: str) -> str:
        """Шифрование данных"""
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Дешифрование данных"""
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка дешифрования: {e}")
            raise


def generate_csv_report(tasks, output_path='reports/report.csv'):
    """
    Генерация отчета в формате CSV
    
    Args:
        tasks: список заданий (объекты Task или словари)
        output_path: путь для сохранения отчета
    """
    # Если путь относительный, создаем его относительно корня проекта
    report_path = Path(output_path)
    if not report_path.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        report_path = project_root / output_path
    report_dir = report_path.parent
    report_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(report_path)
    
    # Подготовка данных
    data = []
    for task in tasks:
        if hasattr(task, '__dict__'):
            # SQLAlchemy объект
            row = {
                'ID задания': task.id,
                'Дата задания': task.task_date.strftime('%Y-%m-%d') if task.task_date else '',
                'Смена': '1-я (8:00-20:00)' if task.shift.value == 1 else '2-я (20:00-8:00)',
                'Начальник': task.manager.full_name if task.manager else f"ID: {task.manager_id}",
                'Сотрудник': task.employee.full_name if task.employee else f"ID: {task.employee_id}",
                'Оборудование': task.equipment.name if task.equipment else f"ID: {task.equipment_id}",
                'Продукция': task.product.name if task.product else f"ID: {task.product_id}",
                'План, шт': task.planned_quantity,
                'Факт, шт': task.actual_quantity,
                'Статус': task.status.value,
                'Создано': task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else '',
                'Получено': task.received_at.strftime('%Y-%m-%d %H:%M:%S') if task.received_at else '',
                'Завершено': task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else '',
            }
        else:
            # Словарь
            row = task
        
        data.append(row)
    
    # Создание DataFrame и сохранение
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    logger.info(f"CSV отчет сохранен: {output_path}")
    return output_path


def _register_cyrillic_font():
    """Регистрирует шрифт с поддержкой кириллицы"""
    font_name = 'CyrillicFont'
    font_bold_name = 'CyrillicFont-Bold'
    
    # Проверяем, не зарегистрирован ли уже шрифт
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name, font_bold_name
    
    # Пути к возможным системным шрифтам с поддержкой кириллицы
    import platform
    system = platform.system()
    
    font_paths = []
    bold_font_paths = []
    
    if system == 'Windows':
        # Windows - стандартные пути к шрифтам
        windir = os.environ.get('WINDIR', 'C:\\Windows')
        font_paths = [
            os.path.join(windir, 'Fonts', 'arial.ttf'),
            os.path.join(windir, 'Fonts', 'Arial.ttf'),
            os.path.join(windir, 'Fonts', 'calibri.ttf'),
            os.path.join(windir, 'Fonts', 'Calibri.ttf'),
        ]
        bold_font_paths = [
            os.path.join(windir, 'Fonts', 'arialbd.ttf'),
            os.path.join(windir, 'Fonts', 'Arial Bold.ttf'),
            os.path.join(windir, 'Fonts', 'calibrib.ttf'),
            os.path.join(windir, 'Fonts', 'Calibri Bold.ttf'),
        ]
    elif system == 'Linux':
        # Linux - стандартные пути к шрифтам
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
        ]
        bold_font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
        ]
    elif system == 'Darwin':  # macOS
        font_paths = [
            '/System/Library/Fonts/Helvetica.ttc',
            '/Library/Fonts/Arial.ttf',
        ]
        bold_font_paths = [
            '/System/Library/Fonts/Helvetica.ttc',
            '/Library/Fonts/Arial Bold.ttf',
        ]
    
    # Пытаемся найти и зарегистрировать обычный шрифт
    regular_font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, path))
                regular_font = font_name
                logger.info(f"Зарегистрирован шрифт для кириллицы: {path}")
                break
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать шрифт {path}: {e}")
                continue
    
    # Пытаемся найти и зарегистрировать жирный шрифт
    bold_font = None
    for path in bold_font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(font_bold_name, path))
                bold_font = font_bold_name
                logger.info(f"Зарегистрирован жирный шрифт для кириллицы: {path}")
                break
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать жирный шрифт {path}: {e}")
                continue
    
    # Если не нашли шрифт, используем встроенные шрифты ReportLab (могут не поддерживать кириллицу)
    if not regular_font:
        logger.warning("Шрифт с поддержкой кириллицы не найден. Кириллические символы могут отображаться некорректно.")
        return 'Helvetica', 'Helvetica-Bold'
    
    return regular_font, (bold_font or regular_font)


def generate_pdf_report(tasks, output_path='reports/report.pdf', title='Отчет по заданиям'):
    """
    Генерация отчета в формате PDF
    
    Args:
        tasks: список заданий (объекты Task или словари)
        output_path: путь для сохранения отчета
        title: заголовок отчета
    """
    # Если путь относительный, создаем его относительно корня проекта
    report_path = Path(output_path)
    if not report_path.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        report_path = project_root / output_path
    report_dir = report_path.parent
    report_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(report_path)
    
    # Регистрируем шрифт с поддержкой кириллицы
    regular_font, bold_font = _register_cyrillic_font()
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Функция для экранирования HTML-специальных символов
    def escape_html(text):
        """Экранирует HTML-специальные символы для безопасного использования в Paragraph"""
        if text is None:
            return ''
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text
    
    # Стиль для заголовка таблицы
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontName=bold_font,
        fontSize=8,
        textColor=colors.whitesmoke,
        alignment=1,  # Center
        leading=10
    )
    
    # Стиль для ячеек таблицы
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName=regular_font,
        fontSize=7,
        alignment=1,  # Center
        leading=8
    )
    
    # Заголовок
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=bold_font,
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph(escape_html(title), title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Дата генерации
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontName=regular_font,
        fontSize=10,
        textColor=colors.grey,
        alignment=1
    )
    story.append(Paragraph(escape_html(f"Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"), date_style))
    story.append(Spacer(1, 1*cm))
    
    # Подготовка данных для таблицы
    # Заголовки таблицы
    headers = ['ID', 'Дата', 'Смена', 'Сотрудник', 'Оборудование', 'Продукция', 'План', 'Факт', 'Статус']
    table_data = [[Paragraph(escape_html(header), header_style) for header in headers]]
    
    for task in tasks:
        if hasattr(task, '__dict__'):
            row = [
                Paragraph(escape_html(str(task.id)), cell_style),
                Paragraph(escape_html(task.task_date.strftime('%d.%m.%Y') if task.task_date else ''), cell_style),
                Paragraph(escape_html('1-я' if task.shift.value == 1 else '2-я'), cell_style),
                Paragraph(escape_html(task.employee.full_name if task.employee else f"ID:{task.employee_id}"), cell_style),
                Paragraph(escape_html(task.equipment.name if task.equipment else f"ID:{task.equipment_id}"), cell_style),
                Paragraph(escape_html(task.product.name if task.product else f"ID:{task.product_id}"), cell_style),
                Paragraph(escape_html(str(task.planned_quantity)), cell_style),
                Paragraph(escape_html(str(task.actual_quantity)), cell_style),
                Paragraph(escape_html(task.status.value), cell_style)
            ]
        else:
            row = [
                Paragraph(escape_html(str(task.get('id', ''))), cell_style),
                Paragraph(escape_html(str(task.get('task_date', ''))), cell_style),
                Paragraph(escape_html(str(task.get('shift', ''))), cell_style),
                Paragraph(escape_html(str(task.get('employee', ''))), cell_style),
                Paragraph(escape_html(str(task.get('equipment', ''))), cell_style),
                Paragraph(escape_html(str(task.get('product', ''))), cell_style),
                Paragraph(escape_html(str(task.get('planned_quantity', ''))), cell_style),
                Paragraph(escape_html(str(task.get('actual_quantity', ''))), cell_style),
                Paragraph(escape_html(str(task.get('status', ''))), cell_style)
            ]
        table_data.append(row)
    
    # Создание таблицы
    table = Table(table_data, colWidths=[1*cm, 2*cm, 1.5*cm, 3*cm, 2.5*cm, 2.5*cm, 1.5*cm, 1.5*cm, 1.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    
    # Построение PDF
    doc.build(story)
    
    logger.info(f"PDF отчет сохранен: {output_path}")
    return output_path
