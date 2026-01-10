#!/usr/bin/env python3
"""
Админ-панель для управления пользователями, оборудованием и продукцией
"""
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import sys
import os

# Добавляем путь к модулям приложения (для совместимости с Docker)
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import DatabaseManager, RoleEnum, engine
from app.core.models import User, Equipment, Product, ProductEquipment, Workshop
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.ext.declarative import declarative_base

# Создаем базовую модель для справочников
DictBase = declarative_base()

class MassName(DictBase):
    __tablename__ = 'mass_names'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)

class Volume(DictBase):
    __tablename__ = 'volumes'
    id = Column(Integer, primary_key=True)
    value = Column(String(50), nullable=False, unique=True)

class Container(DictBase):
    __tablename__ = 'containers'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

class Seal(DictBase):
    __tablename__ = 'seals'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

# Инициализация справочников при первом запуске
def init_dictionaries():
    """Создает таблицы справочников, если их нет"""
        try:
            from app.core.database import engine
            # Используем тот же engine, что и основное приложение
            # Создаем таблицы через SQL напрямую, если их нет
            with engine.connect() as conn:
            # Проверяем и создаем таблицы
            for table_name, table_class in [('mass_names', MassName), ('volumes', Volume), 
                                           ('containers', Container), ('seals', Seal)]:
                try:
                    # Проверяем, существует ли таблица
                    result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                    if not result.fetchone():
                        # Создаем таблицу
                        DictBase.metadata.tables[table_name].create(engine, checkfirst=True)
                except Exception:
                    pass
        DictBase.metadata.create_all(engine, checkfirst=True)
        except Exception as e:
            print(f"Ошибка при создании справочников: {e}")
            # Пробуем создать через SQL
            try:
                from app.core.database import engine
                from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS mass_names (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(200) NOT NULL UNIQUE
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS volumes (
                        id INTEGER PRIMARY KEY,
                        value VARCHAR(50) NOT NULL UNIQUE
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS containers (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS seals (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE
                    )
                """))
                conn.commit()
        except Exception as e2:
            pass

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'admin-panel-secret-key-change-in-production')

# Инициализируем справочники
init_dictionaries()

# Базовый HTML шаблон
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ-панель - Task Manager</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .container .card {
            max-width: 100%;
        }
        /* Для страниц с формами - более узкий контейнер */
        .form-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 8px;
        }
        h1 { margin-bottom: 10px; }
        nav {
            display: flex;
            gap: 15px;
            margin-top: 20px;
        }
        nav a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            transition: background 0.3s;
        }
        nav a:hover, nav a.active {
            background: rgba(255,255,255,0.2);
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
        }
        tr:hover { background: #f8f9fa; }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            font-size: 14px;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn:hover { opacity: 0.9; }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }
        input[type="text"], input[type="number"], select, textarea {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #ced4da;
            border-radius: 6px;
            font-size: 14px;
            background-color: #fff;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
            box-sizing: border-box;
        }
        input[type="text"]:focus, input[type="number"]:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }
        input[type="text"]:hover, input[type="number"]:hover, select:hover, textarea:hover {
            border-color: #adb5bd;
        }
        .form-group label {
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        input[type="text"], input[type="number"], select, textarea {
            min-height: 42px;
        }
        /* Ограничиваем ширину всех элементов формы до размера контейнера */
        .form-group input[type="text"],
        .form-group input[type="number"],
        .form-group select,
        .form-group textarea {
            max-width: 100% !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }
        /* Убеждаемся, что форма не выходит за пределы контейнера */
        .card form {
            max-width: 100%;
            overflow: hidden;
        }
        #name_conditional_field {
            display: block !important;
            margin-bottom: 20px;
        }
        #name_conditional_field input[type="text"] {
            border: 2px solid #3498db !important;
            background-color: #ffffff !important;
            font-size: 15px !important;
            padding: 12px 15px !important;
            min-height: 42px !important;
        }
        #name_conditional_field input[type="text"]:focus {
            border-color: #2980b9 !important;
            box-shadow: 0 0 0 4px rgba(52, 152, 219, 0.2) !important;
            outline: none !important;
        }
        #name_conditional_field input[type="text"]:hover {
            border-color: #2980b9 !important;
        }
        input[type="text"], input[type="number"], select, textarea {
            min-height: 42px;
        }
        #name_conditional_field input[type="text"] {
            border: 2px solid #3498db !important;
            background-color: #ffffff !important;
            font-size: 15px !important;
            padding: 12px 15px !important;
        }
        #name_conditional_field input[type="text"]:focus {
            border-color: #2980b9 !important;
            box-shadow: 0 0 0 4px rgba(52, 152, 219, 0.2) !important;
        }
        .alert {
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .actions { display: flex; gap: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚙️ Админ-панель Task Manager</h1>
            <nav>
                <a href="/" class="{{ 'active' if section == 'users' else '' }}">👥 Пользователи</a>
                <a href="/workshops" class="{{ 'active' if section == 'workshops' else '' }}">🏭 Участки</a>
                <a href="/equipment" class="{{ 'active' if section == 'equipment' else '' }}">🔧 Оборудование</a>
                <a href="/products" class="{{ 'active' if section == 'products' else '' }}">📦 Продукция</a>
                <a href="/dictionaries" class="{{ 'active' if section == 'dictionaries' else '' }}">📚 Справочники</a>
            </nav>
        </header>

        {% if message %}
        <div class="alert alert-{{ message_type }}">{{ message }}</div>
        {% endif %}

        {{ content|safe }}
    </div>
</body>
</html>
"""

def render_page(content, section='users', message=None, message_type='success'):
    return render_template_string(BASE_TEMPLATE, content=content, section=section, message=message, message_type=message_type)

# Роуты
@app.route('/')
def index():
    with DatabaseManager() as db:
        users = db.db.query(User).all()
        users_html = """
        <div class="card">
            <h2>👥 Управление пользователями</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Telegram ID</th>
                        <th>Имя пользователя</th>
                        <th>Полное имя</th>
                        <th>Роль</th>
                        <th>Активен</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        """
        for user in users:
            users_html += f"""
                    <tr>
                        <td>{user.id}</td>
                        <td>{user.telegram_id}</td>
                        <td>{user.username or '-'}</td>
                        <td>{user.full_name or '-'}</td>
                        <td>
                            <select onchange="updateRole({user.id}, this.value)" style="width: auto; padding: 4px;">
                                <option value="employee" {'selected' if user.role.value == 'employee' else ''}>Сотрудник</option>
                                <option value="manager" {'selected' if user.role.value == 'manager' else ''}>Начальник</option>
                                <option value="admin" {'selected' if user.role.value == 'admin' else ''}>Администратор</option>
                            </select>
                        </td>
                        <td>{'Да' if user.is_active else 'Нет'}</td>
                        <td class="actions">
                            <span class="btn btn-primary">✏️ Изменить</span>
                        </td>
                    </tr>
            """
        users_html += """
                </tbody>
            </table>
        </div>
        <script>
        function updateRole(userId, role) {
            fetch('/api/users/' + userId, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({role: role})
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert('Ошибка: ' + data.error);
                    location.reload();
                } else {
                    alert('Роль обновлена!');
                }
            })
            .catch(e => {
                alert('Ошибка: ' + e);
                location.reload();
            });
        }
        </script>
        """
    
    return render_page(users_html, section='users')

@app.route('/equipment')
def equipment_list():
    with DatabaseManager() as db:
        equipment = db.db.query(Equipment).all()
        equipment_html = """
        <div class="card">
            <h2>🔧 Управление оборудованием</h2>
            <a href="/equipment/add" class="btn btn-success">+ Добавить оборудование</a>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Код</th>
                        <th>Участок</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        """
        for item in equipment:
            workshop = db.db.query(Workshop).filter(Workshop.id == item.workshop_id).first() if item.workshop_id else None
            equipment_html += f"""
                    <tr>
                        <td>{item.id}</td>
                        <td>{item.name}</td>
                        <td>{item.code or '-'}</td>
                        <td>{workshop.name if workshop else '-'}</td>
                        <td class="actions">
                            <a href="/equipment/{item.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/equipment/{item.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        equipment_html += """
                </tbody>
            </table>
        </div>
        """
    
    return render_page(equipment_html, section='equipment')

@app.route('/products')
def products_list():
    with DatabaseManager() as db:
        products = db.db.query(Product).all()
        products_html = """
        <div class="card">
            <h2>📦 Управление продукцией</h2>
            <a href="/products/add" class="btn btn-success">+ Добавить продукцию</a>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Категория</th>
                        <th>Оборудование</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        """
        for product in products:
            # Получаем метаданные
            import json
            metadata = {}
            user_code = ''
            if product.code:
                try:
                    data = json.loads(product.code)
                    if isinstance(data, dict) and 'metadata' in data:
                        metadata = data['metadata']
                        user_code = data.get('user_code', '')
                    else:
                        metadata = data
                except (json.JSONDecodeError, TypeError):
                    user_code = product.code
            
            category = metadata.get('category', '-')
            
            # Получаем связанное оборудование
            equipment_list = []
            for pe in product.product_equipment:
                equipment_list.append(pe.equipment.name)
            equipment_str = ', '.join(equipment_list) if equipment_list else '-'
            
            products_html += f"""
                    <tr>
                        <td>{product.id}</td>
                        <td>{product.name}</td>
                        <td>{category}</td>
                        <td>{equipment_str}</td>
                        <td class="actions">
                            <a href="/products/{product.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/products/{product.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        products_html += """
                </tbody>
            </table>
        </div>
        """
    
    return render_page(products_html, section='products')

@app.route('/workshops')
def workshops_list():
    with DatabaseManager() as db:
        workshops = db.db.query(Workshop).all()
        workshops_html = """
        <div class="card">
            <h2>🏭 Управление участками</h2>
            <a href="/workshops/add" class="btn btn-success">+ Добавить участок</a>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Описание</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        """
        for workshop in workshops:
            workshops_html += f"""
                    <tr>
                        <td>{workshop.id}</td>
                        <td>{workshop.name}</td>
                        <td>{workshop.description or '-'}</td>
                        <td class="actions">
                            <a href="/workshops/{workshop.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/workshops/{workshop.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить участок? Все связанное оборудование останется без участка.')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        workshops_html += """
                </tbody>
            </table>
        </div>
        """
    
    return render_page(workshops_html, section='workshops')

@app.route('/workshops/add', methods=['GET', 'POST'])
def add_workshop():
    if request.method == 'POST':
        with DatabaseManager() as db:
            workshop = Workshop(
                name=request.form.get('name'),
                description=request.form.get('description') or None
            )
            db.db.add(workshop)
            db.db.commit()
            return redirect(url_for('workshops_list'))
    
    fields = [
        {'name': 'name', 'label': 'Название участка', 'type': 'text', 'required': True},
        {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
    ]
    return render_form('Добавить участок', fields, '/workshops/add', '/workshops', 'workshops')

@app.route('/workshops/<int:workshop_id>/edit', methods=['GET', 'POST'])
def edit_workshop(workshop_id):
    with DatabaseManager() as db:
        workshop = db.db.query(Workshop).filter(Workshop.id == workshop_id).first()
        if not workshop:
            return redirect(url_for('workshops_list'))
        
        if request.method == 'POST':
            workshop.name = request.form.get('name')
            workshop.description = request.form.get('description') or None
            db.db.commit()
            return redirect(url_for('workshops_list'))
        
        fields = [
            {'name': 'name', 'label': 'Название участка', 'type': 'text', 'required': True},
            {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
        ]
        values = {
            'name': workshop.name,
            'description': workshop.description
        }
        return render_form('Изменить участок', fields, f'/workshops/{workshop_id}/edit', '/workshops', 'workshops', values)

@app.route('/workshops/<int:workshop_id>/delete', methods=['GET'])
def delete_workshop(workshop_id):
    with DatabaseManager() as db:
        workshop = db.db.query(Workshop).filter(Workshop.id == workshop_id).first()
        if workshop:
            # Проверяем, есть ли оборудование на этом участке
            equipment_count = db.db.query(Equipment).filter(Equipment.workshop_id == workshop_id).count()
            if equipment_count > 0:
                # Можно либо не удалять, либо сбросить workshop_id у оборудования
                # Выбираем второй вариант - сбрасываем связь
                db.db.query(Equipment).filter(Equipment.workshop_id == workshop_id).update({Equipment.workshop_id: None})
            
            db.db.delete(workshop)
            db.db.commit()
    return redirect(url_for('workshops_list'))

# Формы
def render_form(title, fields, action_url, back_url, section, values=None):
    form_html = f"""
    <div class="card" style="max-width: 800px; margin: 0 auto;">
        <h2>{title}</h2>
        <form method="POST" action="{action_url}">
    """
    for field in fields:
        value = values.get(field['name'], '') if values else ''
        
        # Проверяем, является ли поле условным
        field_id = None
        if field.get('conditional') and field.get('categories'):
            # Для условных полей создаем обертку с условным отображением
            initial_category = values.get('category', '') if values else ''
            categories = field.get('categories', [])
            # Показываем поле по умолчанию, чтобы оно было видно (JavaScript скроет если нужно)
            initial_display = 'block'
            field_id = f"{field['name']}_conditional_field"
            form_html += f'<div id="{field_id}" style="display: {initial_display};">'
            
        form_html += f"""
            <div class="form-group">
                <label>{field['label']}{' <span style="color: red;">*</span>' if field.get('required') else ''}</label>
        """
        if field['type'] == 'select':
            form_html += f'<select name="{field["name"]}" {"required" if field.get("required") else ""} style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; background-color: #fff; box-sizing: border-box;">'
            form_html += '<option value="">Выберите...</option>'
            for option in field.get('options', []):
                selected = 'selected' if str(value) == str(option['id']) else ''
                form_html += f'<option value="{option["id"]}" {selected}>{option["name"]}</option>'
            form_html += '</select>'
        elif field['type'] == 'textarea':
            form_html += f'<textarea name="{field["name"]}" rows="3" {"required" if field.get("required") else ""} style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; box-sizing: border-box; font-family: inherit;">{value}</textarea>'
        elif field['type'] == 'checkbox':
            checked = 'checked' if value else ''
            form_html += f'<input type="checkbox" name="{field["name"]}" {checked}>'
        elif field['type'] == 'radio':
            form_html += '<div style="display: flex; gap: 20px; flex-wrap: wrap;">'
            for option in field.get('options', []):
                checked = 'checked' if str(value) == str(option['value']) else ''
                form_html += f'''
                <label style="display: flex; align-items: center; gap: 5px;">
                    <input type="radio" name="{field["name"]}" value="{option["value"]}" {checked} {"required" if field.get("required") else ""}>
                    {option["label"]}
                </label>
                '''
            form_html += '</div>'
        elif field['type'] == 'multiselect':
            form_html += f'<select name="{field["name"]}" multiple size="5" style="min-height: 100px; max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; background-color: #fff; box-sizing: border-box;" {"required" if field.get("required") else ""} onchange="removeDuplicates(this)">'
            selected_values = value if isinstance(value, list) else (value.split(',') if value else [])
            # Убираем дубликаты из selected_values
            selected_values = list(dict.fromkeys(selected_values))
            for option in field.get('options', []):
                selected = 'selected' if str(option['id']) in selected_values else ''
                form_html += f'<option value="{option["id"]}" {selected}>{option["name"]}</option>'
            form_html += '</select><small style="display: block; margin-top: 5px; color: #666;">Удерживайте Ctrl (Cmd на Mac) для выбора нескольких элементов</small>'
        elif field['type'] == 'conditional_field':
            # Поле, показываемое условно для определенных категорий
            categories = field.get('categories', [])
            field_def = field.get('field', {})
            field_name = field_def.get('name', '')
            field_value = values.get(field_name, '') if values else ''
            # Определяем начальное состояние видимости на основе выбранной категории
            # Если категория не указана, проверяем, выбрана ли категория по умолчанию
            initial_category = values.get('category', '') if values else ''
            # Если категория не выбрана, показываем поле по умолчанию (на случай, если первая категория - ГП или ТУБА)
            if not initial_category:
                # Проверяем, есть ли выбранная категория в радиокнопках
                initial_display = 'block'  # Показываем по умолчанию, JavaScript скроет если нужно
            else:
                initial_display = 'block' if initial_category in categories else 'none'
            form_html += f'<div id="name_field_group" style="display: {initial_display};">'
            form_html += f'''
                <div class="form-group">
                    <label style="font-weight: bold;">{field_def.get("label", "")} <span style="color: red;">*</span></label>
                    <input type="{field_def.get('type', 'text')}" name="{field_name}" value="{field_value}" {"required" if field_def.get('required') else ""} style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; box-sizing: border-box;">
                </div>
            '''
            form_html += '</div>'
        elif field['type'] == 'conditional_group':
            # Группа полей, показываемая условно через JavaScript
            category = values.get('category', '') if values else ''
            form_html += f'<div id="{field["name"]}_group" style="display: none;">'
            for sub_field in field.get('fields', []):
                sub_value = values.get(sub_field['name'], '') if values else ''
                form_html += f'''
                <div class="form-group">
                    <label>{sub_field["label"]}</label>
                '''
                if sub_field['type'] == 'select':
                    form_html += f'<select name="{sub_field["name"]}" {"required" if sub_field.get("required") else ""} style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; background-color: #fff; box-sizing: border-box;">'
                    form_html += '<option value="">Выберите...</option>'
                    for option in sub_field.get('options', []):
                        selected = 'selected' if str(sub_value) == str(option['id']) else ''
                        form_html += f'<option value="{option["id"]}" {selected}>{option["name"]}</option>'
                    form_html += '</select>'
                elif sub_field['type'] == 'multiselect':
                    form_html += f'<select name="{sub_field["name"]}" multiple size="5" style="min-height: 100px; max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; background-color: #fff; box-sizing: border-box;" {"required" if sub_field.get("required") else ""} onchange="removeDuplicates(this)">'
                    selected_values = sub_value if isinstance(sub_value, list) else (sub_value.split(',') if sub_value else [])
                    # Убираем дубликаты из selected_values
                    selected_values = list(dict.fromkeys(selected_values))
                    for option in sub_field.get('options', []):
                        selected = 'selected' if str(option['id']) in selected_values else ''
                        form_html += f'<option value="{option["id"]}" {selected}>{option["name"]}</option>'
                    form_html += '</select><small style="display: block; margin-top: 5px; color: #666;">Удерживайте Ctrl (Cmd на Mac) для выбора нескольких элементов</small>'
                elif sub_field['type'] == 'text':
                    form_html += f'<input type="text" name="{sub_field["name"]}" value="{sub_value}" style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; box-sizing: border-box;">'
                elif sub_field['type'] == 'number':
                    form_html += f'<input type="number" name="{sub_field["name"]}" value="{sub_value}" step="0.01" style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; box-sizing: border-box;">'
                form_html += '</div>'
            form_html += '</div>'
        elif field['type'] == 'text':
            # Обычное текстовое поле
            required_attr = ''
            if field.get('conditional'):
                # required будет управляться через JavaScript
                required_attr = 'data-required-for="' + ','.join(field.get('categories', [])) + '"'
            else:
                required_attr = 'required' if field.get('required') else ''
            # Улучшенные стили для поля названия продукции
            if field.get('name') == 'name' and field.get('conditional'):
                style_attr = 'style="max-width: 100%; width: 100%; padding: 12px 15px; border: 2px solid #3498db !important; border-radius: 6px; font-size: 15px; box-sizing: border-box; background-color: #ffffff !important; min-height: 42px;"'
            else:
                style_attr = 'style="max-width: 100%; width: 100%; padding: 10px 12px; border: 2px solid #ced4da; border-radius: 6px; font-size: 14px; box-sizing: border-box;"'
            form_html += f'<input type="text" name="{field["name"]}" value="{value}" {required_attr} {style_attr}>'
        
        form_html += '</div>'  # Закрываем form-group
        
        # Закрываем условную обертку, если она была создана
        if field_id and field['type'] != 'conditional_field':
            form_html += '</div>'
        
        # Добавляем JavaScript для управления видимостью полей один раз для всех групп
        if any(f.get('type') in ['conditional_group', 'conditional_field'] for f in fields):
            form_html += '''
            <script>
            function updateFieldsVisibility() {
                const category = document.querySelector('input[name="category"]:checked')?.value || '';
                // Поле "Название продукции" показываем только для ГП и ТУБА
                const nameField = document.getElementById('name_conditional_field');
                if (nameField) {
                    const shouldShow = (category === 'ГП' || category === 'ТУБА');
                    nameField.style.display = shouldShow ? 'block' : 'none';
                    // Управляем required атрибутом
                    const nameInput = nameField.querySelector('input[name="name"]');
                    if (nameInput) {
                        if (shouldShow) {
                            nameInput.setAttribute('required', 'required');
                            nameInput.style.border = '2px solid #ced4da';
                            nameInput.style.display = 'block';
                        } else {
                            nameInput.removeAttribute('required');
                            nameInput.style.display = 'none';
                        }
                    }
                }
                // Условные группы полей
                const massFields = document.getElementById('mass_fields_group');
                if (massFields) massFields.style.display = category === 'МАССА' ? 'block' : 'none';
                const gpFields = document.getElementById('gp_fields_group');
                if (gpFields) gpFields.style.display = category === 'ГП' ? 'block' : 'none';
                const tubeFields = document.getElementById('tube_fields_group');
                if (tubeFields) tubeFields.style.display = category === 'ТУБА' ? 'block' : 'none';
            }
            
            // Функция для удаления дубликатов в multiselect
            function removeDuplicates(selectElement) {
                const selectedValues = Array.from(selectElement.selectedOptions).map(opt => opt.value);
                const uniqueValues = [...new Set(selectedValues)];
                
                // Если есть дубликаты, обновляем выбор
                if (selectedValues.length !== uniqueValues.length) {
                    Array.from(selectElement.options).forEach(opt => {
                        opt.selected = uniqueValues.includes(opt.value);
                    });
                }
            }
            
            document.addEventListener('DOMContentLoaded', function() {
                // Сразу вызываем для установки правильного начального состояния
                updateFieldsVisibility();
                // Устанавливаем обработчики на изменение категории
                document.querySelectorAll('input[name="category"]').forEach(radio => {
                    radio.addEventListener('change', updateFieldsVisibility);
                    // Также вызываем при клике для немедленной реакции
                    radio.addEventListener('click', updateFieldsVisibility);
                });
            });
            </script>
            '''
        else:
            # Для других типов полей
            required_attr = 'required' if field.get('required') else ''
            form_html += f'<input type="{field["type"]}" name="{field["name"]}" value="{value}" {required_attr}>'
        
        form_html += '</div>'
        
        # Закрываем условную обертку, если она была создана
        if field_id and field['type'] != 'conditional_field':
            form_html += '</div>'
    
    form_html += f"""
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{back_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    """
    return render_page(form_html, section=section)

@app.route('/equipment/add', methods=['GET', 'POST'])
def add_equipment():
    if request.method == 'POST':
        with DatabaseManager() as db:
            workshop_id = request.form.get('workshop_id')
            if not workshop_id:
                return redirect(url_for('equipment_list'))
            
            equipment = Equipment(
                name=request.form.get('name'),
                code=request.form.get('code') or None,
                workshop_id=int(workshop_id),
                is_active=True
            )
            db.db.add(equipment)
            db.db.commit()
            return redirect(url_for('equipment_list'))
    
    with DatabaseManager() as db:
        workshops = db.db.query(Workshop).all()
        if not workshops:
            return render_page('<div class="card"><h2>Ошибка</h2><p>Нет доступных участков. Сначала добавьте участок.</p><a href="/workshops/add" class="btn btn-success">Добавить участок</a></div>', section='equipment')
        
        fields = [
            {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
            {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
            {'name': 'workshop_id', 'label': 'Участок', 'type': 'select', 'options': [{'id': w.id, 'name': w.name} for w in workshops], 'required': True}
        ]
        return render_form('Добавить оборудование', fields, '/equipment/add', '/equipment', 'equipment')

@app.route('/equipment/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_equipment(item_id):
    with DatabaseManager() as db:
        equipment = db.db.query(Equipment).filter(Equipment.id == item_id).first()
        if not equipment:
            return redirect(url_for('equipment_list'))
        
        if request.method == 'POST':
            equipment.name = request.form.get('name')
            equipment.code = request.form.get('code') or None
            workshop_id = request.form.get('workshop_id')
            if workshop_id:
                equipment.workshop_id = int(workshop_id)
            if 'is_active' in request.form:
                equipment.is_active = request.form.get('is_active') == 'on'
            db.db.commit()
            return redirect(url_for('equipment_list'))
        
        workshops = db.db.query(Workshop).all()
        fields = [
            {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
            {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
            {'name': 'workshop_id', 'label': 'Участок', 'type': 'select', 'options': [{'id': w.id, 'name': w.name} for w in workshops], 'required': True},
            {'name': 'is_active', 'label': 'Активно', 'type': 'checkbox'}
        ]
        values = {
            'name': equipment.name,
            'code': equipment.code,
            'workshop_id': equipment.workshop_id,
            'is_active': 'on' if equipment.is_active else ''
        }
        return render_form('Изменить оборудование', fields, f'/equipment/{item_id}/edit', '/equipment', 'equipment', values)

@app.route('/equipment/<int:item_id>/delete', methods=['GET'])
def delete_equipment(item_id):
    with DatabaseManager() as db:
        equipment = db.db.query(Equipment).filter(Equipment.id == item_id).first()
        if equipment:
            db.db.delete(equipment)
            db.db.commit()
    return redirect(url_for('equipment_list'))

def get_product_metadata(product):
    """Извлекает метаданные из поля code продукта"""
    import json
    if not product.code:
        return {}, ''
    try:
        data = json.loads(product.code)
        if isinstance(data, dict) and 'metadata' in data:
            # Если код содержит пользовательский код и метаданные
            return data['metadata'], data.get('user_code', '')
        else:
            # Если код содержит только метаданные
            return data, ''
    except (json.JSONDecodeError, TypeError):
        # Если code не JSON, значит это обычный код пользователя
        return {}, product.code

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        with DatabaseManager() as db:
            import json
            # Получаем категорию
            category = request.form.get('category')
            
            # Для категории МАССА название не требуется - будет сгенерировано из наименования массы
            if category == 'МАССА':
                # Получаем наименование массы и используем его как название
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    if mass_name:
                        product_name = mass_name.name
                    else:
                        flash('Необходимо выбрать наименование массы', 'error')
                        return redirect(url_for('add_product'))
                else:
                    flash('Необходимо выбрать наименование массы', 'error')
                    return redirect(url_for('add_product'))
            else:
                # Для ГП и ТУБА название обязательно
                product_name = request.form.get('name', '').strip()
                if not product_name or product_name == '':
                    # Возвращаем пользователя на форму с сообщением об ошибке
                    # Используем ту же сессию db
                    equipment_list = db.db.query(Equipment).filter(Equipment.is_active == True).all()
                    try:
                        mass_names = db.db.query(MassName).all()
                        volumes = db.db.query(Volume).all()
                        containers = db.db.query(Container).all()
                        seals = db.db.query(Seal).all()
                    except Exception:
                        mass_names = []
                        volumes = []
                        containers = []
                        seals = []
                    
                    fields = [
                        {
                            'name': 'name',
                            'label': 'Название продукции',
                            'type': 'text',
                            'required': True,
                            'conditional': True,
                            'categories': ['ГП', 'ТУБА']
                        },
                        {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
                        {
                            'name': 'category',
                            'label': 'Категория',
                            'type': 'radio',
                            'required': True,
                            'options': [
                                {'value': 'МАССА', 'label': 'МАССА'},
                                {'value': 'ГП', 'label': 'ГП'},
                                {'value': 'ТУБА', 'label': 'ТУБА'}
                            ]
                        },
                        {
                            'name': 'mass_fields',
                            'label': '',
                            'type': 'conditional_group',
                            'category': 'МАССА',
                            'fields': [
                                {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'required': True, 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                                {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                            ]
                        },
                        {
                            'name': 'gp_fields',
                            'label': '',
                            'type': 'conditional_group',
                            'category': 'ГП',
                            'fields': [
                                {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                                {'name': 'volume_id', 'label': 'Объём', 'type': 'select', 'options': [{'id': v.id, 'name': v.value} for v in volumes]},
                                {'name': 'container_id', 'label': 'Тара', 'type': 'select', 'options': [{'id': c.id, 'name': c.name} for c in containers]},
                                {'name': 'seal_id', 'label': 'Укупорка', 'type': 'select', 'options': [{'id': s.id, 'name': s.name} for s in seals]},
                                {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                            ]
                        },
                        {
                            'name': 'tube_fields',
                            'label': '',
                            'type': 'conditional_group',
                            'category': 'ТУБА',
                            'fields': [
                                {'name': 'tube_name', 'label': 'Наименование тубы', 'type': 'text'},
                                {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                            ]
                        }
                    ]
                    values = {
                        'category': category or 'МАССА',
                        'name': request.form.get('name', ''),
                        'mass_name_id': request.form.get('mass_name_id', ''),
                        'volume_id': request.form.get('volume_id', ''),
                        'container_id': request.form.get('container_id', ''),
                        'seal_id': request.form.get('seal_id', ''),
                        'tube_name': request.form.get('tube_name', '')
                    }
                    form_content = render_form('Добавить продукцию', fields, '/products/add', '/products', 'products', values)
                    return render_page(form_content, section='products', 
                                 message='Ошибка: Название продукции обязательно для заполнения! Это поле критически важно для категорий ГП и ТУБА.', 
                                 message_type='error')
            
            # Собираем данные в зависимости от категории
            metadata = {'category': category}
            
            if category == 'МАССА':
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    metadata['mass_name'] = mass_name.name if mass_name else None
            elif category == 'ГП':
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    metadata['mass_name'] = mass_name.name if mass_name else None
                
                volume_id = request.form.get('volume_id')
                if volume_id:
                    volume = db.db.query(Volume).filter(Volume.id == int(volume_id)).first()
                    metadata['volume'] = volume.value if volume else None
                
                container_id = request.form.get('container_id')
                if container_id:
                    container = db.db.query(Container).filter(Container.id == int(container_id)).first()
                    metadata['container'] = container.name if container else None
                
                seal_id = request.form.get('seal_id')
                if seal_id:
                    seal = db.db.query(Seal).filter(Seal.id == int(seal_id)).first()
                    metadata['seal'] = seal.name if seal else None
            elif category == 'ТУБА':
                metadata['tube_name'] = request.form.get('tube_name') or None
            
            # Сохраняем код и метаданные
            # Для обеспечения уникальности добавляем имя продукта в код, если пользовательский код не указан
            user_code = request.form.get('code') or None
            if user_code:
                code_data = {'user_code': user_code, 'metadata': metadata}
                final_code = json.dumps(code_data, ensure_ascii=False)
            else:
                # Добавляем имя продукта в метаданные для обеспечения уникальности кода
                metadata['product_name'] = product_name
                final_code = json.dumps(metadata, ensure_ascii=False)
            
            product = Product(
                name=product_name,
                code=final_code
            )
            try:
                db.db.add(product)
                db.db.flush()
                
                # Добавляем связи с оборудованием (убираем дубликаты)
                equipment_ids = request.form.getlist('equipment_ids')
                # Удаляем дубликаты, пустые значения и преобразуем в int
                unique_equipment_ids = []
                seen = set()
                for equipment_id in equipment_ids:
                    if equipment_id and equipment_id not in seen:
                        try:
                            unique_equipment_ids.append(int(equipment_id))
                            seen.add(equipment_id)
                        except (ValueError, TypeError):
                            continue
                
                for equipment_id in unique_equipment_ids:
                    product_equipment = ProductEquipment(
                        product_id=product.id,
                        equipment_id=equipment_id
                    )
                    db.db.add(product_equipment)
                
                db.db.commit()
                flash('Продукт успешно добавлен!', 'success')
                return redirect(url_for('products_list'))
            except Exception as e:
                db.db.rollback()
                import traceback
                error_msg = str(e)
                print(f"Ошибка при сохранении продукта: {error_msg}")
                print(traceback.format_exc())
                flash(f'Ошибка при сохранении: {error_msg}', 'error')
                # Возвращаем форму с данными
                equipment_list = db.db.query(Equipment).filter(Equipment.is_active == True).all()
                try:
                    mass_names = db.db.query(MassName).all()
                    volumes = db.db.query(Volume).all()
                    containers = db.db.query(Container).all()
                    seals = db.db.query(Seal).all()
                except Exception:
                    mass_names = []
                    volumes = []
                    containers = []
                    seals = []
                
                fields = [
                    {
                        'name': 'name',
                        'label': 'Название продукции',
                        'type': 'text',
                        'required': True,
                        'conditional': True,
                        'categories': ['ГП', 'ТУБА']
                    },
                    {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
                    {
                        'name': 'category',
                        'label': 'Категория',
                        'type': 'radio',
                        'required': True,
                        'options': [
                            {'value': 'МАССА', 'label': 'МАССА'},
                            {'value': 'ГП', 'label': 'ГП'},
                            {'value': 'ТУБА', 'label': 'ТУБА'}
                        ]
                    },
                    {
                        'name': 'mass_fields',
                        'label': '',
                        'type': 'conditional_group',
                        'category': 'МАССА',
                        'fields': [
                            {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'required': True, 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                            {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                        ]
                    },
                    {
                        'name': 'gp_fields',
                        'label': '',
                        'type': 'conditional_group',
                        'category': 'ГП',
                        'fields': [
                            {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                            {'name': 'volume_id', 'label': 'Объём', 'type': 'select', 'options': [{'id': v.id, 'name': v.value} for v in volumes]},
                            {'name': 'container_id', 'label': 'Тара', 'type': 'select', 'options': [{'id': c.id, 'name': c.name} for c in containers]},
                            {'name': 'seal_id', 'label': 'Укупорка', 'type': 'select', 'options': [{'id': s.id, 'name': s.name} for s in seals]},
                            {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                        ]
                    },
                    {
                        'name': 'tube_fields',
                        'label': '',
                        'type': 'conditional_group',
                        'category': 'ТУБА',
                        'fields': [
                            {'name': 'tube_name', 'label': 'Наименование тубы', 'type': 'text'},
                            {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                        ]
                    }
                ]
                values = {
                    'category': category or 'МАССА',
                    'name': request.form.get('name', ''),
                    'code': request.form.get('code', ''),
                    'mass_name_id': request.form.get('mass_name_id', ''),
                    'volume_id': request.form.get('volume_id', ''),
                    'container_id': request.form.get('container_id', ''),
                    'seal_id': request.form.get('seal_id', ''),
                    'tube_name': request.form.get('tube_name', '')
                }
                form_content = render_form('Добавить продукцию', fields, '/products/add', '/products', 'products', values)
                return render_page(form_content, section='products', 
                             message=f'Ошибка при сохранении: {error_msg}', 
                             message_type='error')
    
    with DatabaseManager() as db:
        equipment_list = db.db.query(Equipment).filter(Equipment.is_active == True).all()
        
        # Получаем данные для выпадающих списков
        mass_names = db.db.query(MassName).all()
        volumes = db.db.query(Volume).all()
        containers = db.db.query(Container).all()
        seals = db.db.query(Seal).all()
        
        fields = [
            {
                'name': 'name',
                'label': 'Название продукции',
                'type': 'text',
                'required': True,
                'conditional': True,
                'categories': ['ГП', 'ТУБА']
            },
            {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
            {
                'name': 'category',
                'label': 'Категория',
                'type': 'radio',
                'required': True,
                'options': [
                    {'value': 'МАССА', 'label': 'МАССА'},
                    {'value': 'ГП', 'label': 'ГП'},
                    {'value': 'ТУБА', 'label': 'ТУБА'}
                ]
            },
            {
                'name': 'mass_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'МАССА',
                'fields': [
                    {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'required': True, 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            },
            {
                'name': 'gp_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'ГП',
                'fields': [
                    {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                    {'name': 'volume_id', 'label': 'Объём', 'type': 'select', 'options': [{'id': v.id, 'name': v.value} for v in volumes]},
                    {'name': 'container_id', 'label': 'Тара', 'type': 'select', 'options': [{'id': c.id, 'name': c.name} for c in containers]},
                    {'name': 'seal_id', 'label': 'Укупорка', 'type': 'select', 'options': [{'id': s.id, 'name': s.name} for s in seals]},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            },
            {
                'name': 'tube_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'ТУБА',
                'fields': [
                    {'name': 'tube_name', 'label': 'Наименование тубы', 'type': 'text'},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            }
        ]
        return render_form('Добавить продукцию', fields, '/products/add', '/products', 'products')

@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    with DatabaseManager() as db:
        product = db.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return redirect(url_for('products_list'))
        
        if request.method == 'POST':
            import json
            category = request.form.get('category')
            
            # Собираем данные в зависимости от категории
            metadata = {'category': category}
            
            if category == 'МАССА':
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    metadata['mass_name'] = mass_name.name if mass_name else None
            elif category == 'ГП':
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    metadata['mass_name'] = mass_name.name if mass_name else None
                
                volume_id = request.form.get('volume_id')
                if volume_id:
                    volume = db.db.query(Volume).filter(Volume.id == int(volume_id)).first()
                    metadata['volume'] = volume.value if volume else None
                
                container_id = request.form.get('container_id')
                if container_id:
                    container = db.db.query(Container).filter(Container.id == int(container_id)).first()
                    metadata['container'] = container.name if container else None
                
                seal_id = request.form.get('seal_id')
                if seal_id:
                    seal = db.db.query(Seal).filter(Seal.id == int(seal_id)).first()
                    metadata['seal'] = seal.name if seal else None
            elif category == 'ТУБА':
                metadata['tube_name'] = request.form.get('tube_name') or None
            
            # Обновляем название продукта
            if category == 'МАССА':
                # Для МАССА название генерируется из наименования массы
                mass_name_id = request.form.get('mass_name_id')
                if mass_name_id:
                    mass_name = db.db.query(MassName).filter(MassName.id == int(mass_name_id)).first()
                    if mass_name:
                        product.name = mass_name.name
                    else:
                        flash('Необходимо выбрать наименование массы', 'error')
                        return redirect(url_for('edit_product', product_id=product_id))
                else:
                    flash('Необходимо выбрать наименование массы', 'error')
                    return redirect(url_for('edit_product', product_id=product_id))
            else:
                # Для ГП и ТУБА название обязательно
                product_name = request.form.get('name', '').strip()
                if not product_name:
                    flash('Название продукции обязательно для заполнения. Это поле критически важно для категорий ГП и ТУБА.', 'error')
                    return redirect(url_for('edit_product', product_id=product_id))
                product.name = product_name
            
            # Сохраняем код и метаданные
            user_code = request.form.get('code') or None
            if user_code:
                code_data = {'user_code': user_code, 'metadata': metadata}
                product.code = json.dumps(code_data, ensure_ascii=False)
            else:
                # Добавляем имя продукта в метаданные для обеспечения уникальности кода
                metadata['product_name'] = product.name
                product.code = json.dumps(metadata, ensure_ascii=False)
            
            # Удаляем старые связи
            db.db.query(ProductEquipment).filter(ProductEquipment.product_id == product_id).delete()
            
            # Добавляем новые связи с оборудованием (убираем дубликаты)
            equipment_ids = request.form.getlist('equipment_ids')
            # Удаляем дубликаты, пустые значения и преобразуем в int
            unique_equipment_ids = []
            seen = set()
            for equipment_id in equipment_ids:
                if equipment_id and equipment_id not in seen:
                    unique_equipment_ids.append(int(equipment_id))
                    seen.add(equipment_id)
            
            for equipment_id in unique_equipment_ids:
                product_equipment = ProductEquipment(
                    product_id=product.id,
                    equipment_id=equipment_id
                )
                db.db.add(product_equipment)
            
            db.db.commit()
            return redirect(url_for('products_list'))
        
        # Получаем метаданные из code
        metadata, user_code = get_product_metadata(product)
        
        # Получаем текущее связанное оборудование
        current_equipment_ids = [str(pe.equipment_id) for pe in product.product_equipment]
        
        equipment_list = db.db.query(Equipment).filter(Equipment.is_active == True).all()
        
        # Получаем данные для выпадающих списков
        try:
            mass_names = db.db.query(MassName).all()
            volumes = db.db.query(Volume).all()
            containers = db.db.query(Container).all()
            seals = db.db.query(Seal).all()
        except Exception:
            # Если таблицы еще не созданы, используем пустые списки
            mass_names = []
            volumes = []
            containers = []
            seals = []
        
        # Получаем ID из метаданных для предзаполнения формы
        mass_name_id = None
        volume_id = None
        container_id = None
        seal_id = None
        
        if metadata.get('mass_name'):
            mass_name_obj = db.db.query(MassName).filter(MassName.name == metadata['mass_name']).first()
            mass_name_id = mass_name_obj.id if mass_name_obj else None
        
        if metadata.get('volume'):
            volume_obj = db.db.query(Volume).filter(Volume.value == str(metadata['volume'])).first()
            volume_id = volume_obj.id if volume_obj else None
        
        if metadata.get('container'):
            container_obj = db.db.query(Container).filter(Container.name == metadata['container']).first()
            container_id = container_obj.id if container_obj else None
        
        if metadata.get('seal'):
            seal_obj = db.db.query(Seal).filter(Seal.name == metadata['seal']).first()
            seal_id = seal_obj.id if seal_obj else None
        
        fields = [
            {
                'name': 'name',
                'label': 'Название продукции',
                'type': 'text',
                'required': True,
                'conditional': True,
                'categories': ['ГП', 'ТУБА']
            },
            {'name': 'code', 'label': 'Код (опционально)', 'type': 'text'},
            {
                'name': 'category',
                'label': 'Категория',
                'type': 'radio',
                'required': True,
                'options': [
                    {'value': 'МАССА', 'label': 'МАССА'},
                    {'value': 'ГП', 'label': 'ГП'},
                    {'value': 'ТУБА', 'label': 'ТУБА'}
                ]
            },
            {
                'name': 'mass_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'МАССА',
                'fields': [
                    {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'required': True, 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            },
            {
                'name': 'gp_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'ГП',
                'fields': [
                    {'name': 'mass_name_id', 'label': 'Наименование массы', 'type': 'select', 'options': [{'id': m.id, 'name': m.name} for m in mass_names]},
                    {'name': 'volume_id', 'label': 'Объём', 'type': 'select', 'options': [{'id': v.id, 'name': v.value} for v in volumes]},
                    {'name': 'container_id', 'label': 'Тара', 'type': 'select', 'options': [{'id': c.id, 'name': c.name} for c in containers]},
                    {'name': 'seal_id', 'label': 'Укупорка', 'type': 'select', 'options': [{'id': s.id, 'name': s.name} for s in seals]},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            },
            {
                'name': 'tube_fields',
                'label': '',
                'type': 'conditional_group',
                'category': 'ТУБА',
                'fields': [
                    {'name': 'tube_name', 'label': 'Наименование тубы', 'type': 'text'},
                    {'name': 'equipment_ids', 'label': 'Оборудование', 'type': 'multiselect', 'options': [{'id': e.id, 'name': f"{e.name} ({e.code or 'без кода'})"} for e in equipment_list]}
                ]
            }
        ]
        values = {
            'name': product.name,
            'code': user_code,
            'category': metadata.get('category', 'МАССА'),
            'mass_name_id': str(mass_name_id) if mass_name_id else '',
            'volume_id': str(volume_id) if volume_id else '',
            'container_id': str(container_id) if container_id else '',
            'seal_id': str(seal_id) if seal_id else '',
            'tube_name': metadata.get('tube_name', ''),
            'equipment_ids': ','.join(current_equipment_ids)
        }
        return render_form('Изменить продукцию', fields, f'/products/{product_id}/edit', '/products', 'products', values)

@app.route('/products/<int:product_id>/delete', methods=['GET'])
def delete_product(product_id):
    with DatabaseManager() as db:
        product = db.db.query(Product).filter(Product.id == product_id).first()
        if product:
            # Удаляем связи с оборудованием
            db.db.query(ProductEquipment).filter(ProductEquipment.product_id == product_id).delete()
            # Удаляем продукт
            db.db.delete(product)
            db.db.commit()
    return redirect(url_for('products_list'))

# API для обновления роли пользователя
@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    
    with DatabaseManager() as db:
        user = db.db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if 'role' in data:
            try:
                user.role = RoleEnum(data['role'])
            except ValueError:
                return jsonify({'error': f"Неверная роль. Доступные: {[r.value for r in RoleEnum]}"}), 400
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        db.db.commit()
        
        return jsonify({
            'id': user.id,
            'role': user.role.value,
            'is_active': user.is_active
        })

# CRUD для справочников
@app.route('/dictionaries')
def dictionaries_list():
    """Главная страница справочников"""
    html = """
    <div class="card">
        <h2>📚 Управление справочниками</h2>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px;">
            <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                <h3>Наименование массы</h3>
                <a href="/dictionaries/mass_names" class="btn btn-primary">Управление</a>
            </div>
            <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                <h3>Объём</h3>
                <a href="/dictionaries/volumes" class="btn btn-primary">Управление</a>
            </div>
            <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                <h3>Тара</h3>
                <a href="/dictionaries/containers" class="btn btn-primary">Управление</a>
            </div>
            <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                <h3>Укупорка</h3>
                <a href="/dictionaries/seals" class="btn btn-primary">Управление</a>
            </div>
        </div>
    </div>
    """
    return render_page(html, section='dictionaries')

# Наименование массы
@app.route('/dictionaries/mass_names')
def mass_names_list():
    with DatabaseManager() as db:
        items = db.db.query(MassName).all()
        html = """
        <div class="card">
            <h2>Наименование массы</h2>
            <a href="/dictionaries/mass_names/add" class="btn btn-success">+ Добавить</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Название</th><th>Действия</th></tr>
                </thead>
                <tbody>
        """
        for item in items:
            html += f"""
                    <tr>
                        <td>{item.id}</td>
                        <td>{item.name}</td>
                        <td class="actions">
                            <a href="/dictionaries/mass_names/{item.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/dictionaries/mass_names/{item.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
        return render_page(html, section='dictionaries')

@app.route('/dictionaries/mass_names/add', methods=['GET', 'POST'])
def add_mass_name():
    if request.method == 'POST':
        with DatabaseManager() as db:
            item = MassName(name=request.form.get('name'))
            db.db.add(item)
            db.db.commit()
            return redirect(url_for('mass_names_list'))
    fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
    return render_form('Добавить наименование массы', fields, '/dictionaries/mass_names/add', '/dictionaries/mass_names', 'dictionaries')

@app.route('/dictionaries/mass_names/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_mass_name(item_id):
    with DatabaseManager() as db:
        item = db.db.query(MassName).filter(MassName.id == item_id).first()
        if not item:
            return redirect(url_for('mass_names_list'))
        if request.method == 'POST':
            item.name = request.form.get('name')
            db.db.commit()
            return redirect(url_for('mass_names_list'))
        fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
        return render_form('Изменить наименование массы', fields, f'/dictionaries/mass_names/{item_id}/edit', '/dictionaries/mass_names', 'dictionaries', {'name': item.name})

@app.route('/dictionaries/mass_names/<int:item_id>/delete', methods=['GET'])
def delete_mass_name(item_id):
    with DatabaseManager() as db:
        item = db.db.query(MassName).filter(MassName.id == item_id).first()
        if item:
            db.db.delete(item)
            db.db.commit()
    return redirect(url_for('mass_names_list'))

# Объём
@app.route('/dictionaries/volumes')
def volumes_list():
    with DatabaseManager() as db:
        items = db.db.query(Volume).all()
        html = """
        <div class="card">
            <h2>Объём</h2>
            <a href="/dictionaries/volumes/add" class="btn btn-success">+ Добавить</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Значение</th><th>Действия</th></tr>
                </thead>
                <tbody>
        """
        for item in items:
            html += f"""
                    <tr>
                        <td>{item.id}</td>
                        <td>{item.value}</td>
                        <td class="actions">
                            <a href="/dictionaries/volumes/{item.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/dictionaries/volumes/{item.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
        return render_page(html, section='dictionaries')

@app.route('/dictionaries/volumes/add', methods=['GET', 'POST'])
def add_volume():
    if request.method == 'POST':
        with DatabaseManager() as db:
            item = Volume(value=request.form.get('value'))
            db.db.add(item)
            db.db.commit()
            return redirect(url_for('volumes_list'))
    fields = [{'name': 'value', 'label': 'Значение', 'type': 'text', 'required': True}]
    return render_form('Добавить объём', fields, '/dictionaries/volumes/add', '/dictionaries/volumes', 'dictionaries')

@app.route('/dictionaries/volumes/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_volume(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Volume).filter(Volume.id == item_id).first()
        if not item:
            return redirect(url_for('volumes_list'))
        if request.method == 'POST':
            item.value = request.form.get('value')
            db.db.commit()
            return redirect(url_for('volumes_list'))
        fields = [{'name': 'value', 'label': 'Значение', 'type': 'text', 'required': True}]
        return render_form('Изменить объём', fields, f'/dictionaries/volumes/{item_id}/edit', '/dictionaries/volumes', 'dictionaries', {'value': item.value})

@app.route('/dictionaries/volumes/<int:item_id>/delete', methods=['GET'])
def delete_volume(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Volume).filter(Volume.id == item_id).first()
        if item:
            db.db.delete(item)
            db.db.commit()
    return redirect(url_for('volumes_list'))

# Тара
@app.route('/dictionaries/containers')
def containers_list():
    with DatabaseManager() as db:
        items = db.db.query(Container).all()
        html = """
        <div class="card">
            <h2>Тара</h2>
            <a href="/dictionaries/containers/add" class="btn btn-success">+ Добавить</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Название</th><th>Действия</th></tr>
                </thead>
                <tbody>
        """
        for item in items:
            html += f"""
                    <tr>
                        <td>{item.id}</td>
                        <td>{item.name}</td>
                        <td class="actions">
                            <a href="/dictionaries/containers/{item.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/dictionaries/containers/{item.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
        return render_page(html, section='dictionaries')

@app.route('/dictionaries/containers/add', methods=['GET', 'POST'])
def add_container():
    if request.method == 'POST':
        with DatabaseManager() as db:
            item = Container(name=request.form.get('name'))
            db.db.add(item)
            db.db.commit()
            return redirect(url_for('containers_list'))
    fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
    return render_form('Добавить тару', fields, '/dictionaries/containers/add', '/dictionaries/containers', 'dictionaries')

@app.route('/dictionaries/containers/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_container(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Container).filter(Container.id == item_id).first()
        if not item:
            return redirect(url_for('containers_list'))
        if request.method == 'POST':
            item.name = request.form.get('name')
            db.db.commit()
            return redirect(url_for('containers_list'))
        fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
        return render_form('Изменить тару', fields, f'/dictionaries/containers/{item_id}/edit', '/dictionaries/containers', 'dictionaries', {'name': item.name})

@app.route('/dictionaries/containers/<int:item_id>/delete', methods=['GET'])
def delete_container(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Container).filter(Container.id == item_id).first()
        if item:
            db.db.delete(item)
            db.db.commit()
    return redirect(url_for('containers_list'))

# Укупорка
@app.route('/dictionaries/seals')
def seals_list():
    with DatabaseManager() as db:
        items = db.db.query(Seal).all()
        html = """
        <div class="card">
            <h2>Укупорка</h2>
            <a href="/dictionaries/seals/add" class="btn btn-success">+ Добавить</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Название</th><th>Действия</th></tr>
                </thead>
                <tbody>
        """
        for item in items:
            html += f"""
                    <tr>
                        <td>{item.id}</td>
                        <td>{item.name}</td>
                        <td class="actions">
                            <a href="/dictionaries/seals/{item.id}/edit" class="btn btn-primary">✏️ Изменить</a>
                            <a href="/dictionaries/seals/{item.id}/delete" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️ Удалить</a>
                        </td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
        return render_page(html, section='dictionaries')

@app.route('/dictionaries/seals/add', methods=['GET', 'POST'])
def add_seal():
    if request.method == 'POST':
        with DatabaseManager() as db:
            item = Seal(name=request.form.get('name'))
            db.db.add(item)
            db.db.commit()
            return redirect(url_for('seals_list'))
    fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
    return render_form('Добавить укупорку', fields, '/dictionaries/seals/add', '/dictionaries/seals', 'dictionaries')

@app.route('/dictionaries/seals/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_seal(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Seal).filter(Seal.id == item_id).first()
        if not item:
            return redirect(url_for('seals_list'))
        if request.method == 'POST':
            item.name = request.form.get('name')
            db.db.commit()
            return redirect(url_for('seals_list'))
        fields = [{'name': 'name', 'label': 'Название', 'type': 'text', 'required': True}]
        return render_form('Изменить укупорку', fields, f'/dictionaries/seals/{item_id}/edit', '/dictionaries/seals', 'dictionaries', {'name': item.name})

@app.route('/dictionaries/seals/<int:item_id>/delete', methods=['GET'])
def delete_seal(item_id):
    with DatabaseManager() as db:
        item = db.db.query(Seal).filter(Seal.id == item_id).first()
        if item:
            db.db.delete(item)
            db.db.commit()
    return redirect(url_for('seals_list'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5051, debug=True)
