"""
Модели данных для базы данных
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class RoleEnum(enum.Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    EMPLOYEE = 'employee'


class ShiftEnum(enum.Enum):
    FIRST = 1  # 8:00 - 20:00
    SECOND = 2  # 20:00 - 8:00


class TaskStatusEnum(enum.Enum):
    CREATED = 'created'
    RECEIVED = 'received'
    COMPLETED = 'completed'
    CLOSED = 'closed'


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.EMPLOYEE)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    assigned_tasks = relationship('Task', foreign_keys='Task.employee_id', back_populates='employee')
    created_tasks = relationship('Task', foreign_keys='Task.manager_id', back_populates='manager')
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, role={self.role.value})>"


class Workshop(Base):
    """Модель участка цеха"""
    __tablename__ = 'workshops'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equipment = relationship('Equipment', back_populates='workshop')
    
    def __repr__(self):
        return f"<Workshop(name={self.name})>"


class Equipment(Base):
    """Модель оборудования"""
    __tablename__ = 'equipment'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True)
    workshop_id = Column(Integer, ForeignKey('workshops.id'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workshop = relationship('Workshop', back_populates='equipment')
    tasks = relationship('Task', back_populates='equipment')
    product_equipment = relationship('ProductEquipment', back_populates='equipment')
    
    def __repr__(self):
        return f"<Equipment(name={self.name}, workshop_id={self.workshop_id})>"


class Product(Base):
    """Модель продукции"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True)
    default_equipment_id = Column(Integer, ForeignKey('equipment.id'))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    default_equipment = relationship('Equipment', foreign_keys=[default_equipment_id])
    tasks = relationship('Task', back_populates='product')
    product_equipment = relationship('ProductEquipment', back_populates='product')
    
    def __repr__(self):
        return f"<Product(name={self.name})>"


class ProductEquipment(Base):
    """Модель связи продукции и оборудования (многие ко многим)"""
    __tablename__ = 'product_equipment'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    equipment_id = Column(Integer, ForeignKey('equipment.id'), nullable=False)
    
    # Relationships
    product = relationship('Product', back_populates='product_equipment')
    equipment = relationship('Equipment', back_populates='product_equipment')
    
    def __repr__(self):
        return f"<ProductEquipment(product_id={self.product_id}, equipment_id={self.equipment_id})>"


class Task(Base):
    """Модель задания"""
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    manager_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    employee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    equipment_id = Column(Integer, ForeignKey('equipment.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    planned_quantity = Column(Float, nullable=False)
    actual_quantity = Column(Float, default=0.0)
    shift = Column(Enum(ShiftEnum), nullable=False)
    task_date = Column(DateTime, nullable=False)
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.CREATED)
    received_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(1000))
    
    # Relationships
    manager = relationship('User', foreign_keys=[manager_id], back_populates='created_tasks')
    employee = relationship('User', foreign_keys=[employee_id], back_populates='assigned_tasks')
    equipment = relationship('Equipment', back_populates='tasks')
    product = relationship('Product', back_populates='tasks')
    
    def __repr__(self):
        return f"<Task(id={self.id}, status={self.status.value}, planned={self.planned_quantity})>"


class Notification(Base):
    """Модель уведомлений"""
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User')
    task = relationship('Task')
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, is_read={self.is_read})>"
