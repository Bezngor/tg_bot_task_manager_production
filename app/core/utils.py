"""
Вспомогательные утилиты
"""
import logging
import os
from datetime import datetime, date, timedelta, timezone, timedelta as td
from pathlib import Path
from cryptography.fernet import Fernet

# Попытка использовать zoneinfo (Python 3.9+), иначе pytz
try:
    from zoneinfo import ZoneInfo
    try:
        TIMEZONE = ZoneInfo("Europe/Moscow")
    except Exception:
        # Если zoneinfo не может загрузить tzdata, пробуем pytz
        import pytz
        TIMEZONE = pytz.timezone("Europe/Moscow")
except (ImportError, ModuleNotFoundError):
    try:
        import pytz
        TIMEZONE = pytz.timezone("Europe/Moscow")
    except ImportError:
        # Fallback: используем UTC+3 через timedelta
        TIMEZONE = timezone(td(hours=3))
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd
from .config import ENCRYPTION_KEY

def get_now_utc3() -> datetime:
    """Получить текущее время в UTC+3"""
    try:
        if hasattr(TIMEZONE, 'localize'):
            # pytz
            return TIMEZONE.localize(datetime.now())
        else:
            # zoneinfo или timezone
            return datetime.now(TIMEZONE)
    except Exception:
        # Fallback: используем UTC+3 через timedelta
        return datetime.now(timezone(td(hours=3)))

def get_today_utc3() -> date:
    """Получить текущую дату в UTC+3"""
    return get_now_utc3().date()

def get_yesterday_utc3() -> date:
    """Получить вчерашнюю дату в UTC+3"""
    return get_today_utc3() - timedelta(days=1)

def get_period_dates(period_type: str) -> tuple[date, date]:
    """
    Получить даты начала и конца периода
    
    Args:
        period_type: 'yesterday', 'week', 'month'
    
    Returns:
        tuple: (date_from, date_to) - обе даты включительно
    """
    today = get_today_utc3()
    yesterday = get_yesterday_utc3()
    
    if period_type == 'yesterday':
        # Вчера - от начала вчерашнего дня до конца вчерашнего дня (обе смены)
        return yesterday, yesterday
    
    elif period_type == 'week':
        # Неделя - с понедельника текущей недели до вчера включительно
        # Понедельник - это день недели 0 в Python (weekday())
        current_weekday = today.weekday()
        # Находим понедельник текущей недели
        days_from_monday = current_weekday  # 0 для понедельника, 6 для воскресенья
        week_start = today - timedelta(days=days_from_monday)
        return week_start, yesterday
    
    elif period_type == 'month':
        # Месяц - с 1-го числа текущего месяца до вчера включительно
        month_start = date(today.year, today.month, 1)
        return month_start, yesterday
    
    else:
        raise ValueError(f"Неизвестный тип периода: {period_type}")

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


def generate_csv_report(tasks, output_path='reports/report.csv', period_from=None, period_to=None):
    """
    Генерация отчета в формате CSV
    
    Args:
        tasks: список заданий (объекты Task или словари)
        output_path: путь для сохранения отчета
        period_from: дата начала периода (date)
        period_to: дата окончания периода (date)
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
            planned = task.planned_quantity or 0
            actual = task.actual_quantity or 0
            delta = actual - planned
            
            row = {
                'ID': task.id,
                'Дата': task.task_date.strftime('%d.%m.%Y') if task.task_date else '',
                'Смена': '1-я' if task.shift.value == 1 else '2-я',
                'Сотрудник': task.employee.full_name if task.employee else f"ID: {task.employee_id}",
                'Оборудование': task.equipment.name if task.equipment else f"ID: {task.equipment_id}",
                'Продукция': task.product.name if task.product else f"ID: {task.product_id}",
                'План': planned,
                'Факт': actual,
                'Дельта': delta,
                'Статус': task.status.value,
            }
        else:
            # Словарь
            planned = task.get('planned_quantity', 0) or 0
            actual = task.get('actual_quantity', 0) or 0
            delta = actual - planned
            row = {
                'ID': task.get('id', ''),
                'Дата': task.get('task_date', ''),
                'Смена': task.get('shift', ''),
                'Сотрудник': task.get('employee', ''),
                'Оборудование': task.get('equipment', ''),
                'Продукция': task.get('product', ''),
                'План': planned,
                'Факт': actual,
                'Дельта': delta,
                'Статус': task.get('status', ''),
            }
        
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


def generate_pdf_report(tasks, output_path='reports/report.pdf', title='Отчет по заданиям', period_from=None, period_to=None):
    """
    Генерация отчета в формате PDF
    
    Args:
        tasks: список заданий (объекты Task или словари)
        output_path: путь для сохранения отчета
        title: заголовок отчета
        period_from: дата начала периода (date)
        period_to: дата окончания периода (date)
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
    story.append(Spacer(1, 0.3*cm))
    
    # Период отчета и дата генерации
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontName=regular_font,
        fontSize=10,
        textColor=colors.grey,
        alignment=1
    )
    
    period_text = ""
    if period_from and period_to:
        if period_from == period_to:
            period_text = f"Период: {period_from.strftime('%d.%m.%Y')}"
        else:
            period_text = f"Период: {period_from.strftime('%d.%m.%Y')} - {period_to.strftime('%d.%m.%Y')}"
    
    report_time = get_now_utc3().strftime('%d.%m.%Y %H:%M')
    
    if period_text:
        story.append(Paragraph(escape_html(period_text), date_style))
        story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(escape_html(f"Сформировано: {report_time}"), date_style))
    story.append(Spacer(1, 1*cm))
    
    # Подготовка данных для таблицы
    # Заголовки таблицы
    headers = ['ID', 'Дата', 'Смена', 'Сотрудник', 'Оборудование', 'Продукция', 'План', 'Факт', 'Дельта', 'Статус']
    table_data = [[Paragraph(escape_html(header), header_style) for header in headers]]
    
    for task in tasks:
        if hasattr(task, '__dict__'):
            planned = task.planned_quantity or 0
            actual = task.actual_quantity or 0
            delta = actual - planned
            
            row = [
                Paragraph(escape_html(str(task.id)), cell_style),
                Paragraph(escape_html(task.task_date.strftime('%d.%m.%Y') if task.task_date else ''), cell_style),
                Paragraph(escape_html('1-я' if task.shift.value == 1 else '2-я'), cell_style),
                Paragraph(escape_html(task.employee.full_name if task.employee else f"ID:{task.employee_id}"), cell_style),
                Paragraph(escape_html(task.equipment.name if task.equipment else f"ID:{task.equipment_id}"), cell_style),
                Paragraph(escape_html(task.product.name if task.product else f"ID:{task.product_id}"), cell_style),
                Paragraph(escape_html(str(planned)), cell_style),
                Paragraph(escape_html(str(actual)), cell_style),
                Paragraph(escape_html(str(delta)), cell_style),
                Paragraph(escape_html(task.status.value), cell_style)
            ]
        else:
            planned = task.get('planned_quantity', 0) or 0
            actual = task.get('actual_quantity', 0) or 0
            delta = actual - planned
            
            row = [
                Paragraph(escape_html(str(task.get('id', ''))), cell_style),
                Paragraph(escape_html(str(task.get('task_date', ''))), cell_style),
                Paragraph(escape_html(str(task.get('shift', ''))), cell_style),
                Paragraph(escape_html(str(task.get('employee', ''))), cell_style),
                Paragraph(escape_html(str(task.get('equipment', ''))), cell_style),
                Paragraph(escape_html(str(task.get('product', ''))), cell_style),
                Paragraph(escape_html(str(planned)), cell_style),
                Paragraph(escape_html(str(actual)), cell_style),
                Paragraph(escape_html(str(delta)), cell_style),
                Paragraph(escape_html(str(task.get('status', ''))), cell_style)
            ]
        table_data.append(row)
    
    # Создание таблицы (добавлена колонка Дельта)
    table = Table(table_data, colWidths=[0.8*cm, 2*cm, 1.2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 1.2*cm, 1.2*cm, 1.2*cm, 1.2*cm])
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
