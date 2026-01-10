"""
REST API для работы с системой управления заданиями
"""
from flask import Flask, jsonify, request
from flask_restx import Api, Resource, fields, Namespace
from datetime import datetime, date
from database import DatabaseManager, RoleEnum, ShiftEnum, TaskStatusEnum
from models import User, Task, Equipment, Product
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from utils import logger, generate_csv_report, generate_pdf_report

app = Flask(__name__)
api = Api(
    app,
    version='1.0',
    title='Task Manager API',
    description='REST API для системы управления заданиями цеха',
    doc='/swagger/'
)

# Namespace для задач
tasks_ns = Namespace('tasks', description='Операции с заданиями')
api.add_namespace(tasks_ns)

# Namespace для пользователей
users_ns = Namespace('users', description='Операции с пользователями')
api.add_namespace(users_ns)

# Namespace для отчетов
reports_ns = Namespace('reports', description='Генерация отчетов')
api.add_namespace(reports_ns)

# Модели данных для Swagger
task_model = api.model('Task', {
    'id': fields.Integer(description='ID задания'),
    'manager_id': fields.Integer(description='ID начальника'),
    'employee_id': fields.Integer(description='ID сотрудника'),
    'equipment_id': fields.Integer(description='ID оборудования'),
    'product_id': fields.Integer(description='ID продукции'),
    'planned_quantity': fields.Float(description='Плановое количество'),
    'actual_quantity': fields.Float(description='Фактическое количество'),
    'shift': fields.Integer(description='Смена (1 или 2)'),
    'task_date': fields.DateTime(description='Дата задания'),
    'status': fields.String(description='Статус задания'),
    'created_at': fields.DateTime(description='Дата создания'),
    'received_at': fields.DateTime(description='Дата получения'),
    'completed_at': fields.DateTime(description='Дата завершения'),
    'notes': fields.String(description='Примечания')
})

task_create_model = api.model('TaskCreate', {
    'manager_id': fields.Integer(required=True, description='ID начальника'),
    'employee_id': fields.Integer(required=True, description='ID сотрудника'),
    'equipment_id': fields.Integer(required=True, description='ID оборудования'),
    'product_id': fields.Integer(required=True, description='ID продукции'),
    'planned_quantity': fields.Float(required=True, description='Плановое количество'),
    'shift': fields.Integer(required=True, description='Смена (1 или 2)'),
    'task_date': fields.String(required=True, description='Дата задания (YYYY-MM-DD)'),
    'notes': fields.String(description='Примечания')
})

task_update_model = api.model('TaskUpdate', {
    'status': fields.String(description='Статус задания'),
    'actual_quantity': fields.Float(description='Фактическое количество')
})

user_model = api.model('User', {
    'id': fields.Integer(description='ID пользователя'),
    'telegram_id': fields.Integer(description='Telegram ID'),
    'username': fields.String(description='Имя пользователя'),
    'full_name': fields.String(description='Полное имя'),
    'role': fields.String(description='Роль'),
    'is_active': fields.Boolean(description='Активен ли пользователь'),
    'created_at': fields.DateTime(description='Дата создания')
})


@tasks_ns.route('')
class TaskList(Resource):
    """Список заданий"""
    
    @api.doc('list_tasks')
    @api.param('manager_id', 'ID начальника')
    @api.param('employee_id', 'ID сотрудника')
    @api.param('status', 'Статус задания')
    @api.marshal_list_with(task_model)
    def get(self):
        """Получить список заданий"""
        manager_id = request.args.get('manager_id', type=int)
        employee_id = request.args.get('employee_id', type=int)
        status = request.args.get('status')
        
        with DatabaseManager() as db:
            if manager_id:
                status_enum = TaskStatusEnum(status) if status else None
                tasks = db.get_tasks_by_manager(manager_id, status_enum)
            elif employee_id:
                status_enum = TaskStatusEnum(status) if status else None
                tasks = db.get_tasks_by_employee(employee_id, status_enum)
            else:
                tasks = db.db.query(Task).all()
            
            result = []
            for task in tasks:
                result.append({
                    'id': task.id,
                    'manager_id': task.manager_id,
                    'employee_id': task.employee_id,
                    'equipment_id': task.equipment_id,
                    'product_id': task.product_id,
                    'planned_quantity': task.planned_quantity,
                    'actual_quantity': task.actual_quantity,
                    'shift': task.shift.value,
                    'task_date': task.task_date.isoformat() if task.task_date else None,
                    'status': task.status.value,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'received_at': task.received_at.isoformat() if task.received_at else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'notes': task.notes
                })
            
            return result
    
    @api.doc('create_task')
    @api.expect(task_create_model)
    @api.marshal_with(task_model, code=201)
    def post(self):
        """Создать новое задание"""
        data = request.json
        
        try:
            task_date = datetime.strptime(data['task_date'], '%Y-%m-%d').date()
            shift = ShiftEnum(data['shift'])
            
            with DatabaseManager() as db:
                task = db.create_task(
                    manager_id=data['manager_id'],
                    employee_id=data['employee_id'],
                    equipment_id=data['equipment_id'],
                    product_id=data['product_id'],
                    planned_quantity=data['planned_quantity'],
                    shift=shift,
                    task_date=datetime.combine(task_date, datetime.min.time()),
                    notes=data.get('notes')
                )
                
                return {
                    'id': task.id,
                    'manager_id': task.manager_id,
                    'employee_id': task.employee_id,
                    'equipment_id': task.equipment_id,
                    'product_id': task.product_id,
                    'planned_quantity': task.planned_quantity,
                    'actual_quantity': task.actual_quantity,
                    'shift': task.shift.value,
                    'task_date': task.task_date.isoformat() if task.task_date else None,
                    'status': task.status.value,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'notes': task.notes
                }, 201
        except Exception as e:
            logger.error(f"Ошибка создания задания: {e}")
            return {'error': str(e)}, 400


@tasks_ns.route('/<int:task_id>')
@api.param('task_id', 'ID задания')
class TaskDetail(Resource):
    """Детали задания"""
    
    @api.doc('get_task')
    @api.marshal_with(task_model)
    def get(self, task_id):
        """Получить задание по ID"""
        with DatabaseManager() as db:
            task = db.get_task_by_id(task_id)
            if not task:
                return {'error': 'Задание не найдено'}, 404
            
            return {
                'id': task.id,
                'manager_id': task.manager_id,
                'employee_id': task.employee_id,
                'equipment_id': task.equipment_id,
                'product_id': task.product_id,
                'planned_quantity': task.planned_quantity,
                'actual_quantity': task.actual_quantity,
                'shift': task.shift.value,
                'task_date': task.task_date.isoformat() if task.task_date else None,
                'status': task.status.value,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'received_at': task.received_at.isoformat() if task.received_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'notes': task.notes
            }
    
    @api.doc('update_task')
    @api.expect(task_update_model)
    @api.marshal_with(task_model)
    def put(self, task_id):
        """Обновить задание"""
        data = request.json
        
        with DatabaseManager() as db:
            task = db.get_task_by_id(task_id)
            if not task:
                return {'error': 'Задание не найдено'}, 404
            
            if 'status' in data:
                status = TaskStatusEnum(data['status'])
                db.update_task_status(task_id, status)
            
            if 'actual_quantity' in data:
                db.update_task_actual_quantity(task_id, data['actual_quantity'])
            
            task = db.get_task_by_id(task_id)
            return {
                'id': task.id,
                'manager_id': task.manager_id,
                'employee_id': task.employee_id,
                'equipment_id': task.equipment_id,
                'product_id': task.product_id,
                'planned_quantity': task.planned_quantity,
                'actual_quantity': task.actual_quantity,
                'shift': task.shift.value,
                'task_date': task.task_date.isoformat() if task.task_date else None,
                'status': task.status.value,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'received_at': task.received_at.isoformat() if task.received_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'notes': task.notes
            }


@users_ns.route('')
class UserList(Resource):
    """Список пользователей"""
    
    @api.doc('list_users')
    @api.param('role', 'Роль пользователя (admin, manager, employee)')
    @api.marshal_list_with(user_model)
    def get(self):
        """Получить список пользователей"""
        try:
            role = request.args.get('role')
            
            with DatabaseManager() as db:
                if role:
                    try:
                        role_enum = RoleEnum(role.lower())  # Приводим к нижнему регистру
                        if role_enum == RoleEnum.EMPLOYEE:
                            users = db.get_all_employees()
                        elif role_enum == RoleEnum.MANAGER:
                            users = db.get_all_managers()
                        else:
                            users = db.db.query(User).filter(User.role == role_enum).all()
                    except ValueError:
                        # Неверная роль - возвращаем ошибку
                        return {'error': f'Неверная роль: {role}. Доступные роли: admin, manager, employee'}, 400
                else:
                    users = db.db.query(User).all()
                
                result = []
                for user in users:
                    result.append({
                        'id': user.id,
                        'telegram_id': user.telegram_id,
                        'username': user.username,
                        'full_name': user.full_name,
                        'role': user.role.value,
                        'is_active': user.is_active,
                        'created_at': user.created_at.isoformat() if user.created_at else None
                    })
                
                return result
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return {'error': f'Внутренняя ошибка сервера: {str(e)}'}, 500


@users_ns.route('/<int:user_id>')
@api.param('user_id', 'ID пользователя')
class UserDetail(Resource):
    """Детали пользователя"""
    
    @api.doc('get_user')
    @api.marshal_with(user_model)
    def get(self, user_id):
        """Получить пользователя по ID"""
        with DatabaseManager() as db:
            user = db.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {'error': 'Пользователь не найден'}, 404
            
            return {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'role': user.role.value,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }


@reports_ns.route('/generate')
class ReportGenerate(Resource):
    """Генерация отчетов"""
    
    @api.doc('generate_report')
    @api.param('manager_id', 'ID начальника', required=True)
    @api.param('format', 'Формат отчета (csv или pdf)', required=False, default='csv')
    @api.param('date_from', 'Дата начала (YYYY-MM-DD)', required=False)
    @api.param('date_to', 'Дата окончания (YYYY-MM-DD)', required=False)
    def get(self):
        """Сгенерировать отчет"""
        manager_id = request.args.get('manager_id', type=int)
        format_type = request.args.get('format', 'csv').lower()
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        if not manager_id:
            return {'error': 'manager_id обязателен'}, 400
        
        with DatabaseManager() as db:
            tasks = db.get_tasks_by_manager(manager_id)
            
            # Фильтрация по датам
            if date_from:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                tasks = [t for t in tasks if t.task_date >= date_from_obj]
            
            if date_to:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                tasks = [t for t in tasks if t.task_date <= date_to_obj]
            
            if not tasks:
                return {'error': 'Нет заданий для отчета'}, 404
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'pdf':
                file_path = generate_pdf_report(
                    tasks,
                    f'reports/report_manager_{manager_id}_{timestamp}.pdf'
                )
            else:
                file_path = generate_csv_report(
                    tasks,
                    f'reports/report_manager_{manager_id}_{timestamp}.csv'
                )
            
            return {
                'success': True,
                'file_path': file_path,
                'format': format_type,
                'tasks_count': len(tasks)
            }


@api.route('/equipment')
class EquipmentList(Resource):
    """Список оборудования"""
    
    @api.doc('list_equipment')
    @api.param('workshop_id', 'ID участка')
    def get(self):
        """Получить список оборудования"""
        workshop_id = request.args.get('workshop_id', type=int)
        
        with DatabaseManager() as db:
            equipment_list = db.get_all_equipment(workshop_id)
            
            result = []
            for eq in equipment_list:
                result.append({
                    'id': eq.id,
                    'name': eq.name,
                    'code': eq.code,
                    'workshop_id': eq.workshop_id,
                    'workshop_name': eq.workshop.name if eq.workshop else None,
                    'is_active': eq.is_active
                })
            
            return result


@api.route('/products')
class ProductList(Resource):
    """Список продукции"""
    
    @api.doc('list_products')
    def get(self):
        """Получить список продукции"""
        with DatabaseManager() as db:
            products = db.get_all_products()
            
            result = []
            for product in products:
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'code': product.code,
                    'default_equipment_id': product.default_equipment_id,
                    'is_active': product.is_active
                })
            
            return result


@app.route('/health')
def health_check():
    """Проверка здоровья API"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200


if __name__ == '__main__':
    # Инициализация БД при запуске API
    from database import init_db
    init_db()
    
    logger.info(f"Запуск Flask API на {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
