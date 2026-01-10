#!/usr/bin/env python3
"""
Админ-панель для управления пользователями, оборудованием и продукцией
"""
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import sys
import os

# Добавляем путь к модулям приложения
sys.path.insert(0, '/app')

from database import DatabaseManager, RoleEnum
from models import User, Equipment, Product, Workshop

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'admin-panel-secret-key-change-in-production')

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
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
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
                <a href="/equipment" class="{{ 'active' if section == 'equipment' else '' }}">🔧 Оборудование</a>
                <a href="/products" class="{{ 'active' if section == 'products' else '' }}">📦 Продукция</a>
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
                        <th>Участок</th>
                        <th>Описание</th>
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
                        <td>{workshop.name if workshop else '-'}</td>
                        <td>{item.description or '-'}</td>
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
                        <th>Единица измерения</th>
                        <th>Описание</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        """
        for product in products:
            products_html += f"""
                    <tr>
                        <td>{product.id}</td>
                        <td>{product.name}</td>
                        <td>{product.unit or '-'}</td>
                        <td>{product.description or '-'}</td>
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

# Формы
def render_form(title, fields, action_url, back_url, section, values=None):
    form_html = f"""
    <div class="card">
        <h2>{title}</h2>
        <form method="POST" action="{action_url}">
    """
    for field in fields:
        value = values.get(field['name'], '') if values else ''
        form_html += f"""
            <div class="form-group">
                <label>{field['label']}</label>
        """
        if field['type'] == 'select':
            form_html += f'<select name="{field["name"]}" {"required" if field.get("required") else ""}>'
            form_html += '<option value="">Выберите...</option>'
            for option in field.get('options', []):
                selected = 'selected' if str(value) == str(option['id']) else ''
                form_html += f'<option value="{option["id"]}" {selected}>{option["name"]}</option>'
            form_html += '</select>'
        elif field['type'] == 'textarea':
            form_html += f'<textarea name="{field["name"]}" rows="3" {"required" if field.get("required") else ""}>{value}</textarea>'
        else:
            form_html += f'<input type="{field["type"]}" name="{field["name"]}" value="{value}" {"required" if field.get("required") else ""}>'
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
            equipment = Equipment(
                name=request.form.get('name'),
                workshop_id=int(request.form.get('workshop_id')) if request.form.get('workshop_id') else None,
                description=request.form.get('description') or None
            )
            db.db.add(equipment)
            db.db.commit()
            return redirect(url_for('equipment_list'))
    
    with DatabaseManager() as db:
        workshops = db.db.query(Workshop).all()
        fields = [
            {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
            {'name': 'workshop_id', 'label': 'Участок', 'type': 'select', 'options': [{'id': w.id, 'name': w.name} for w in workshops]},
            {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
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
            equipment.workshop_id = int(request.form.get('workshop_id')) if request.form.get('workshop_id') else None
            equipment.description = request.form.get('description') or None
            db.db.commit()
            return redirect(url_for('equipment_list'))
        
        workshops = db.db.query(Workshop).all()
        fields = [
            {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
            {'name': 'workshop_id', 'label': 'Участок', 'type': 'select', 'options': [{'id': w.id, 'name': w.name} for w in workshops]},
            {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
        ]
        values = {
            'name': equipment.name,
            'workshop_id': equipment.workshop_id,
            'description': equipment.description
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

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        with DatabaseManager() as db:
            product = Product(
                name=request.form.get('name'),
                unit=request.form.get('unit') or None,
                description=request.form.get('description') or None
            )
            db.db.add(product)
            db.db.commit()
            return redirect(url_for('products_list'))
    
    fields = [
        {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
        {'name': 'unit', 'label': 'Единица измерения (кг, шт, л и т.д.)', 'type': 'text'},
        {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
    ]
    return render_form('Добавить продукцию', fields, '/products/add', '/products', 'products')

@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    with DatabaseManager() as db:
        product = db.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return redirect(url_for('products_list'))
        
        if request.method == 'POST':
            product.name = request.form.get('name')
            product.unit = request.form.get('unit') or None
            product.description = request.form.get('description') or None
            db.db.commit()
            return redirect(url_for('products_list'))
        
        fields = [
            {'name': 'name', 'label': 'Название', 'type': 'text', 'required': True},
            {'name': 'unit', 'label': 'Единица измерения', 'type': 'text'},
            {'name': 'description', 'label': 'Описание', 'type': 'textarea'}
        ]
        values = {
            'name': product.name,
            'unit': product.unit,
            'description': product.description
        }
        return render_form('Изменить продукцию', fields, f'/products/{product_id}/edit', '/products', 'products', values)

@app.route('/products/<int:product_id>/delete', methods=['GET'])
def delete_product(product_id):
    with DatabaseManager() as db:
        product = db.db.query(Product).filter(Product.id == product_id).first()
        if product:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5051, debug=True)
