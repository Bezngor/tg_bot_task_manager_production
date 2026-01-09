"""
Модуль для работы с базой данных
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, User, Workshop, Equipment, Product, ProductEquipment, Task, Notification, RoleEnum, ShiftEnum, TaskStatusEnum
from config import DATABASE_URL
from utils import logger
from datetime import datetime

# Создание движка БД
engine = create_engine(DATABASE_URL, echo=False)

# Создание фабрики сессий
SessionLocal = scoped_session(sessionmaker(bind=engine))


def init_db():
    """Инициализация базы данных - создание всех таблиц"""
    try:
        Base.metadata.create_all(engine)
        logger.info("База данных инициализирована успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return False


def get_db():
    """Получение сессии БД"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass


def close_db(db):
    """Закрытие сессии БД"""
    if db:
        db.close()


class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.db = get_db()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    # === User operations ===
    def get_user_by_telegram_id(self, telegram_id: int):
        """Получить пользователя по Telegram ID"""
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()
    
    def create_user(self, telegram_id: int, username: str = None, full_name: str = None, role: RoleEnum = RoleEnum.EMPLOYEE):
        """Создать нового пользователя"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=role
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Создан пользователь: {user}")
        return user
    
    def get_all_employees(self):
        """Получить всех сотрудников"""
        return self.db.query(User).filter(User.role == RoleEnum.EMPLOYEE, User.is_active == True).all()
    
    def get_all_managers(self):
        """Получить всех начальников"""
        return self.db.query(User).filter(User.role == RoleEnum.MANAGER, User.is_active == True).all()
    
    # === Workshop operations ===
    def get_all_workshops(self):
        """Получить все участки"""
        return self.db.query(Workshop).all()
    
    def get_workshop_by_id(self, workshop_id: int):
        """Получить участок по ID"""
        return self.db.query(Workshop).filter(Workshop.id == workshop_id).first()
    
    # === Equipment operations ===
    def get_all_equipment(self, workshop_id: int = None):
        """Получить все оборудование, опционально отфильтровать по участку"""
        query = self.db.query(Equipment).filter(Equipment.is_active == True)
        if workshop_id:
            query = query.filter(Equipment.workshop_id == workshop_id)
        return query.all()
    
    def get_equipment_by_id(self, equipment_id: int):
        """Получить оборудование по ID"""
        return self.db.query(Equipment).filter(Equipment.id == equipment_id).first()
    
    # === Product operations ===
    def get_all_products(self):
        """Получить всю продукцию"""
        return self.db.query(Product).filter(Product.is_active == True).all()
    
    def get_product_by_id(self, product_id: int):
        """Получить продукцию по ID"""
        return self.db.query(Product).filter(Product.id == product_id).first()
    
    def get_equipment_for_product(self, product_id: int):
        """Получить доступное оборудование для продукции"""
        product = self.get_product_by_id(product_id)
        if not product:
            return []
        
        # Получаем связанное оборудование
        product_equipment = self.db.query(ProductEquipment).filter(
            ProductEquipment.product_id == product_id
        ).all()
        
        equipment_ids = [pe.equipment_id for pe in product_equipment]
        if not equipment_ids:
            # Если нет связей, возвращаем оборудование по умолчанию
            if product.default_equipment_id:
                return [product.default_equipment]
            return []
        
        return self.db.query(Equipment).filter(Equipment.id.in_(equipment_ids)).all()
    
    # === Task operations ===
    def create_task(self, manager_id: int, employee_id: int, equipment_id: int, 
                   product_id: int, planned_quantity: float, shift: ShiftEnum, 
                   task_date: datetime, notes: str = None):
        """Создать новое задание"""
        task = Task(
            manager_id=manager_id,
            employee_id=employee_id,
            equipment_id=equipment_id,
            product_id=product_id,
            planned_quantity=planned_quantity,
            shift=shift,
            task_date=task_date,
            notes=notes,
            status=TaskStatusEnum.CREATED
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"Создано задание: {task}")
        return task
    
    def get_task_by_id(self, task_id: int):
        """Получить задание по ID"""
        return self.db.query(Task).filter(Task.id == task_id).first()
    
    def get_tasks_by_employee(self, employee_id: int, status: TaskStatusEnum = None):
        """Получить задания сотрудника"""
        query = self.db.query(Task).filter(Task.employee_id == employee_id)
        if status:
            query = query.filter(Task.status == status)
        return query.order_by(Task.task_date.desc()).all()
    
    def get_tasks_by_manager(self, manager_id: int, status: TaskStatusEnum = None):
        """Получить задания начальника"""
        query = self.db.query(Task).filter(Task.manager_id == manager_id)
        if status:
            query = query.filter(Task.status == status)
        return query.order_by(Task.task_date.desc()).all()
    
    def update_task_status(self, task_id: int, status: TaskStatusEnum):
        """Обновить статус задания"""
        task = self.get_task_by_id(task_id)
        if not task:
            return None
        
        task.status = status
        if status == TaskStatusEnum.RECEIVED:
            task.received_at = datetime.utcnow()
        elif status == TaskStatusEnum.COMPLETED:
            task.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"Обновлен статус задания {task_id}: {status.value}")
        return task
    
    def update_task_actual_quantity(self, task_id: int, actual_quantity: float):
        """Обновить фактическое количество выполненной продукции"""
        task = self.get_task_by_id(task_id)
        if not task:
            return None
        
        task.actual_quantity = actual_quantity
        task.status = TaskStatusEnum.COMPLETED
        task.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"Обновлено фактическое количество для задания {task_id}: {actual_quantity}")
        return task
    
    # === Notification operations ===
    def create_notification(self, user_id: int, task_id: int, message: str):
        """Создать уведомление"""
        notification = Notification(
            user_id=user_id,
            task_id=task_id,
            message=message
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        logger.info(f"Создано уведомление для пользователя {user_id}")
        return notification
    
    def get_unread_notifications(self, user_id: int):
        """Получить непрочитанные уведомления пользователя"""
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).order_by(Notification.created_at.desc()).all()
    
    def mark_notification_read(self, notification_id: int):
        """Отметить уведомление как прочитанное"""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_read = True
            self.db.commit()
        return notification


def init_sample_data():
    """Инициализация тестовых данных (для разработки)"""
    db = get_db()
    try:
        # Проверяем, есть ли уже данные
        if db.query(Workshop).count() > 0:
            logger.info("Тестовые данные уже существуют")
            return
        
        # Создаем участки
        workshop1 = Workshop(name="Участок №1", description="Основной участок производства")
        workshop2 = Workshop(name="Участок №2", description="Вспомогательный участок")
        db.add_all([workshop1, workshop2])
        db.commit()
        
        # Создаем оборудование
        equipment1 = Equipment(name="Станок А", code="EQ-001", workshop_id=workshop1.id)
        equipment2 = Equipment(name="Станок Б", code="EQ-002", workshop_id=workshop1.id)
        equipment3 = Equipment(name="Пресс В", code="EQ-003", workshop_id=workshop2.id)
        db.add_all([equipment1, equipment2, equipment3])
        db.commit()
        
        # Создаем продукцию
        product1 = Product(name="Изделие А", code="PRD-001", default_equipment_id=equipment1.id)
        product2 = Product(name="Изделие Б", code="PRD-002", default_equipment_id=equipment2.id)
        product3 = Product(name="Изделие В", code="PRD-003", default_equipment_id=equipment3.id)
        db.add_all([product1, product2, product3])
        db.commit()
        
        # Связываем продукцию с оборудованием
        pe1 = ProductEquipment(product_id=product1.id, equipment_id=equipment1.id)
        pe2 = ProductEquipment(product_id=product2.id, equipment_id=equipment2.id)
        pe3 = ProductEquipment(product_id=product3.id, equipment_id=equipment3.id)
        db.add_all([pe1, pe2, pe3])
        db.commit()
        
        logger.info("Тестовые данные успешно созданы")
    except Exception as e:
        logger.error(f"Ошибка создания тестовых данных: {e}")
        db.rollback()
    finally:
        db.close()
