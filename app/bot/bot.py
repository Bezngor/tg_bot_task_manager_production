"""
Основной файл Telegram-бота
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path для корректных импортов
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
from datetime import datetime, date
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import Conflict, NetworkError, TimedOut

from app.core.config import TELEGRAM_BOT_TOKEN, Roles, Shifts
from app.core.database import DatabaseManager, RoleEnum, ShiftEnum, TaskStatusEnum
from app.core.models import User
from app.core.utils import logger, generate_csv_report, generate_pdf_report, get_period_dates, get_now_utc3

# Состояния для ConversationHandler
SELECTING_EQUIPMENT, SELECTING_PRODUCT, ENTERING_QUANTITY, SELECTING_EMPLOYEE, SELECTING_SHIFT, CONFIRMING_TASK = range(6)
SELECTING_TASK_FOR_CONFIRM, ENTERING_ACTUAL_QUANTITY = range(6, 8)
SELECTING_STATUS = 8  # Состояние для выбора статуса заданий
SELECTING_REPORT_PERIOD = 9  # Состояние для выбора периода отчета
SELECTING_REPORT_FORMAT = 10  # Состояние для выбора формата отчета
ENTERING_REPORT_DATE_FROM = 11  # Состояние для ввода даты начала кастомного периода
ENTERING_REPORT_DATE_TO = 12  # Состояние для ввода даты конца кастомного периода

# Глобальные переменные для хранения данных при создании задания
task_data = {}


class Command:
    """Базовый класс для паттерна Command"""
    
    def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выполнение команды"""
        raise NotImplementedError


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    with DatabaseManager() as db:
        db_user = db.get_user_by_telegram_id(user.id)
        
        if not db_user:
            # Регистрация нового пользователя
            db_user = db.create_user(
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name or user.username or f"User {user.id}",
                role=RoleEnum.EMPLOYEE  # По умолчанию сотрудник
            )
            message = f"Добро пожаловать, {user.first_name}!\n\nВы зарегистрированы как сотрудник."
        else:
            role_name = {"admin": "Администратор", "manager": "Начальник", "employee": "Сотрудник"}
            message = f"Добро пожаловать обратно, {user.first_name}!\n\nВаша роль: {role_name.get(db_user.role.value, 'Неизвестна')}"
    
    keyboard = get_main_keyboard(db_user.role.value if db_user else 'employee')
    await update.message.reply_text(message, reply_markup=keyboard)
    logger.info(f"Пользователь {user.id} выполнил команду /start")


def get_main_keyboard(role: str):
    """Получить главную клавиатуру в зависимости от роли"""
    if role in ['admin', 'manager']:
        buttons = [
            [KeyboardButton("📋 Создать задание"), KeyboardButton("📊 Мои задания")],
            [KeyboardButton("📈 Отчет"), KeyboardButton("🔔 Уведомления")]
        ]
    else:
        buttons = [
            [KeyboardButton("📋 Мои задания"), KeyboardButton("✅ Подтвердить задание")],
            [KeyboardButton("📝 Отчитаться"), KeyboardButton("🔔 Уведомления")]
        ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def role_required(required_roles: list):
    """Декоратор для проверки роли пользователя"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            with DatabaseManager() as db:
                db_user = db.get_user_by_telegram_id(user.id)
                if not db_user or db_user.role.value not in required_roles:
                    await update.message.reply_text("❌ У вас нет доступа к этой команде.")
                    return
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


@role_required(['admin', 'manager'])
async def create_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания задания (только для начальника)"""
    global task_data
    task_data[update.effective_user.id] = {}
    
    with DatabaseManager() as db:
        workshops = db.get_all_workshops()
        if not workshops:
            await update.message.reply_text("❌ В системе нет участков. Обратитесь к администратору.")
            return ConversationHandler.END
        
        # Получаем оборудование
        equipment_list = db.get_all_equipment()
        if not equipment_list:
            await update.message.reply_text("❌ В системе нет оборудования. Обратитесь к администратору.")
            return ConversationHandler.END
        
        # Создаем клавиатуру с оборудованием
        keyboard = []
        for eq in equipment_list:
            workshop_name = eq.workshop.name if eq.workshop else "Без участка"
            keyboard.append([InlineKeyboardButton(
                f"{eq.name} ({workshop_name})",
                callback_data=f"eq_{eq.id}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 Создание задания\n\nВыберите оборудование:",
            reply_markup=reply_markup
        )
        return SELECTING_EQUIPMENT


async def select_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора оборудования"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Создание задания отменено.")
        task_data.pop(update.effective_user.id, None)
        return ConversationHandler.END
    
    equipment_id = int(query.data.split("_")[1])
    task_data[update.effective_user.id]['equipment_id'] = equipment_id
    
    with DatabaseManager() as db:
        products = db.get_all_products()
        if not products:
            await query.edit_message_text("❌ В системе нет продукции. Обратитесь к администратору.")
            task_data.pop(update.effective_user.id, None)
            return ConversationHandler.END
        
        # Фильтруем продукцию, доступную для выбранного оборудования
        available_products = []
        for product in products:
            equipment_for_product = db.get_equipment_for_product(product.id)
            if any(eq.id == equipment_id for eq in equipment_for_product) or product.default_equipment_id == equipment_id:
                available_products.append(product)
        
        if not available_products:
            await query.edit_message_text("❌ Для выбранного оборудования нет доступной продукции.")
            task_data.pop(update.effective_user.id, None)
            return ConversationHandler.END
        
        keyboard = []
        for product in available_products:
            keyboard.append([InlineKeyboardButton(product.name, callback_data=f"prod_{product.id}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Выберите продукцию:",
            reply_markup=reply_markup
        )
        return SELECTING_PRODUCT


async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора продукции"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Создание задания отменено.")
        task_data.pop(update.effective_user.id, None)
        return ConversationHandler.END
    
    product_id = int(query.data.split("_")[1])
    task_data[update.effective_user.id]['product_id'] = product_id
    
    await query.edit_message_text("Введите количество продукции (число):")
    return ENTERING_QUANTITY


async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода количества"""
    try:
        quantity = float(update.message.text.replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("❌ Количество должно быть больше нуля. Введите корректное значение:")
            return ENTERING_QUANTITY
        
        task_data[update.effective_user.id]['planned_quantity'] = quantity
        
        with DatabaseManager() as db:
            employees = db.get_all_employees()
            if not employees:
                await update.message.reply_text("❌ В системе нет сотрудников.")
                task_data.pop(update.effective_user.id, None)
                return ConversationHandler.END
            
            keyboard = []
            for emp in employees:
                keyboard.append([InlineKeyboardButton(
                    emp.full_name or f"ID: {emp.telegram_id}",
                    callback_data=f"emp_{emp.id}"
                )])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Выберите ответственного сотрудника:",
                reply_markup=reply_markup
            )
            return SELECTING_EMPLOYEE
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return ENTERING_QUANTITY


async def select_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора сотрудника"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Создание задания отменено.")
        task_data.pop(update.effective_user.id, None)
        return ConversationHandler.END
    
    employee_id = int(query.data.split("_")[1])
    task_data[update.effective_user.id]['employee_id'] = employee_id
    
    keyboard = [
        [InlineKeyboardButton("1-я смена (8:00-20:00)", callback_data="shift_1")],
        [InlineKeyboardButton("2-я смена (20:00-8:00)", callback_data="shift_2")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Выберите смену:",
        reply_markup=reply_markup
    )
    return SELECTING_SHIFT


async def select_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора смены"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Создание задания отменено.")
        task_data.pop(update.effective_user.id, None)
        return ConversationHandler.END
    
    shift = int(query.data.split("_")[1])
    task_data[update.effective_user.id]['shift'] = ShiftEnum(shift)
    task_data[update.effective_user.id]['task_date'] = date.today()
    
    # Формируем подтверждение
    with DatabaseManager() as db:
        equipment = db.get_equipment_by_id(task_data[update.effective_user.id]['equipment_id'])
        product = db.get_product_by_id(task_data[update.effective_user.id]['product_id'])
        employee = db.db.query(User).filter(User.id == task_data[update.effective_user.id]['employee_id']).first()
        
        shift_name = "1-я смена (8:00-20:00)" if shift == 1 else "2-я смена (20:00-8:00)"
        
        message = f"📋 Подтвердите создание задания:\n\n"
        message += f"Оборудование: {equipment.name}\n"
        message += f"Продукция: {product.name}\n"
        message += f"Количество: {task_data[update.effective_user.id]['planned_quantity']}\n"
        message += f"Сотрудник: {employee.full_name or f'ID: {employee.telegram_id}'}\n"
        message += f"Смена: {shift_name}\n"
        message += f"Дата: {task_data[update.effective_user.id]['task_date'].strftime('%d.%m.%Y')}"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_task")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
        return CONFIRMING_TASK


async def confirm_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение создания задания"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Создание задания отменено.")
        task_data.pop(update.effective_user.id, None)
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    data = task_data.get(user_id, {})
    
    if not all(k in data for k in ['equipment_id', 'product_id', 'planned_quantity', 'employee_id', 'shift', 'task_date']):
        await query.edit_message_text("❌ Ошибка: не все данные заполнены.")
        task_data.pop(user_id, None)
        return ConversationHandler.END
    
    with DatabaseManager() as db:
        manager = db.get_user_by_telegram_id(user_id)
        
        # Создаем задание
        task = db.create_task(
            manager_id=manager.id,
            employee_id=data['employee_id'],
            equipment_id=data['equipment_id'],
            product_id=data['product_id'],
            planned_quantity=data['planned_quantity'],
            shift=data['shift'],
            task_date=datetime.combine(data['task_date'], datetime.min.time()),
            notes=None
        )
        
        # Отправляем уведомление сотруднику
        employee = db.db.query(User).filter(User.id == data['employee_id']).first()
        if employee:
            equipment = db.get_equipment_by_id(data['equipment_id'])
            product = db.get_product_by_id(data['product_id'])
            shift_name = "1-я смена (8:00-20:00)" if data['shift'].value == 1 else "2-я смена (20:00-8:00)"
            
            notification_msg = f"📋 Вам назначено новое задание №{task.id}\n\n"
            notification_msg += f"Оборудование: {equipment.name}\n"
            notification_msg += f"Продукция: {product.name}\n"
            notification_msg += f"Количество: {data['planned_quantity']}\n"
            notification_msg += f"Смена: {shift_name}\n"
            notification_msg += f"Дата: {data['task_date'].strftime('%d.%m.%Y')}"
            
            db.create_notification(employee.id, task.id, notification_msg)
            
            # Отправляем уведомление сотруднику в Telegram
            try:
                await context.bot.send_message(
                    chat_id=employee.telegram_id,
                    text=f"🔔 {notification_msg}",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления сотруднику: {e}")
        
        await query.edit_message_text(f"✅ Задание №{task.id} успешно создано и отправлено сотруднику!")
        task_data.pop(user_id, None)
        logger.info(f"Создано задание {task.id} менеджером {manager.telegram_id}")
    
    return ConversationHandler.END


@role_required(['admin', 'manager'])
async def my_tasks_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало просмотра заданий начальника с выбором статуса"""
    user = update.effective_user
    with DatabaseManager() as db:
        manager = db.get_user_by_telegram_id(user.id)
        if not manager:
            await update.message.reply_text("❌ Пользователь не найден.")
            return ConversationHandler.END
        
        # Проверяем, есть ли вообще задания
        all_tasks = db.get_tasks_by_manager(manager.id)
        if not all_tasks:
            await update.message.reply_text("📋 У вас пока нет созданных заданий.")
            return ConversationHandler.END
        
        # Показываем клавиатуру для выбора статуса
        keyboard = [
            [InlineKeyboardButton("📋 Все задания", callback_data="mgr_status_all")],
            [InlineKeyboardButton("🆕 Созданные (новые)", callback_data="mgr_status_created")],
            [InlineKeyboardButton("✅ Полученные (в работе)", callback_data="mgr_status_received")],
            [InlineKeyboardButton("✔️ Завершенные", callback_data="mgr_status_completed")],
            [InlineKeyboardButton("🔒 Закрытые", callback_data="mgr_status_closed")],
            [InlineKeyboardButton("❌ Отмена", callback_data="mgr_status_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 Выберите статус заданий для просмотра:",
            reply_markup=reply_markup
        )
        return SELECTING_STATUS


@role_required(['admin', 'manager'])
async def show_manager_tasks_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение заданий начальника по выбранному статусу"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "mgr_status_cancel":
        await query.edit_message_text("❌ Просмотр заданий отменен.")
        return ConversationHandler.END
    
    user = update.effective_user
    status_param = query.data.replace("mgr_status_", "")
    
    with DatabaseManager() as db:
        manager = db.get_user_by_telegram_id(user.id)
        if not manager:
            await query.edit_message_text("❌ Пользователь не найден.")
            return ConversationHandler.END
        
        # Определяем статус для фильтрации
        status_filter = None
        status_name = "Все"
        if status_param != "all":
            try:
                status_filter = TaskStatusEnum(status_param)
                status_names = {
                    "created": "Созданные",
                    "received": "Полученные",
                    "completed": "Завершенные",
                    "closed": "Закрытые"
                }
                status_name = status_names.get(status_param, status_param)
            except ValueError:
                status_filter = None
        
        # Получаем задания с фильтром
        tasks = db.get_tasks_by_manager(manager.id, status=status_filter)
        
        if not tasks:
            status_text = f"📋 У вас нет заданий со статусом '{status_name}'."
            await query.edit_message_text(status_text)
            return ConversationHandler.END
        
        # Формируем сообщение с заданиями
        message = f"📋 Ваши задания ({status_name}):\n\n"
        status_emoji = {"created": "🆕", "received": "✅", "completed": "✔️", "closed": "🔒"}
        
        for task in tasks[:15]:  # Показываем до 15 заданий
            emoji = status_emoji.get(task.status.value, '❓')
            message += f"{emoji} Задание №{task.id}\n"
            message += f"   Сотрудник: {task.employee.full_name if task.employee else 'N/A'}\n"
            message += f"   Оборудование: {task.equipment.name if task.equipment else 'N/A'}\n"
            message += f"   Продукция: {task.product.name if task.product else 'N/A'}\n"
            message += f"   План: {task.planned_quantity}"
            if task.actual_quantity:
                message += f" | Факт: {task.actual_quantity}"
            message += f"\n"
            message += f"   Статус: {task.status.value}\n"
            message += f"   Дата: {task.task_date.strftime('%d.%m.%Y') if task.task_date else 'N/A'}\n\n"
        
        if len(tasks) > 15:
            message += f"\n... и еще {len(tasks) - 15} заданий"
        
        await query.edit_message_text(message)
        return ConversationHandler.END


async def my_tasks_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало просмотра заданий сотрудника с выбором статуса"""
    user = update.effective_user
    with DatabaseManager() as db:
        employee = db.get_user_by_telegram_id(user.id)
        if not employee:
            await update.message.reply_text("❌ Пользователь не найден.")
            return ConversationHandler.END
        
        # Проверяем, есть ли вообще задания
        all_tasks = db.get_tasks_by_employee(employee.id)
        if not all_tasks:
            await update.message.reply_text("📋 У вас нет заданий.")
            return ConversationHandler.END
        
        # Показываем клавиатуру для выбора статуса
        keyboard = [
            [InlineKeyboardButton("📋 Все задания", callback_data="status_all")],
            [InlineKeyboardButton("🆕 Созданные (новые)", callback_data="status_created")],
            [InlineKeyboardButton("✅ Полученные (в работе)", callback_data="status_received")],
            [InlineKeyboardButton("✔️ Завершенные", callback_data="status_completed")],
            [InlineKeyboardButton("🔒 Закрытые", callback_data="status_closed")],
            [InlineKeyboardButton("❌ Отмена", callback_data="status_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 Выберите статус заданий для просмотра:",
            reply_markup=reply_markup
        )
        return SELECTING_STATUS


async def show_tasks_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение заданий по выбранному статусу"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "status_cancel":
        await query.edit_message_text("❌ Просмотр заданий отменен.")
        return ConversationHandler.END
    
    user = update.effective_user
    status_param = query.data.replace("status_", "")
    
    with DatabaseManager() as db:
        employee = db.get_user_by_telegram_id(user.id)
        if not employee:
            await query.edit_message_text("❌ Пользователь не найден.")
            return ConversationHandler.END
        
        # Определяем статус для фильтрации
        status_filter = None
        status_name = "Все"
        if status_param != "all":
            try:
                status_filter = TaskStatusEnum(status_param)
                status_names = {
                    "created": "Созданные",
                    "received": "Полученные",
                    "completed": "Завершенные",
                    "closed": "Закрытые"
                }
                status_name = status_names.get(status_param, status_param)
            except ValueError:
                status_filter = None
        
        # Получаем задания с фильтром
        tasks = db.get_tasks_by_employee(employee.id, status=status_filter)
        
        if not tasks:
            status_text = f"📋 У вас нет заданий со статусом '{status_name}'."
            await query.edit_message_text(status_text)
            return ConversationHandler.END
        
        # Формируем сообщение с заданиями
        message = f"📋 Ваши задания ({status_name}):\n\n"
        status_emoji = {"created": "🆕", "received": "✅", "completed": "✔️", "closed": "🔒"}
        
        for task in tasks[:15]:  # Показываем до 15 заданий
            emoji = status_emoji.get(task.status.value, '❓')
            message += f"{emoji} Задание №{task.id}\n"
            message += f"   Оборудование: {task.equipment.name if task.equipment else 'N/A'}\n"
            message += f"   Продукция: {task.product.name if task.product else 'N/A'}\n"
            message += f"   Количество: {task.planned_quantity}"
            if task.actual_quantity:
                message += f" | Факт: {task.actual_quantity}"
            message += f"\n"
            message += f"   Статус: {task.status.value}\n"
            message += f"   Дата: {task.task_date.strftime('%d.%m.%Y') if task.task_date else 'N/A'}\n\n"
        
        if len(tasks) > 15:
            message += f"\n... и еще {len(tasks) - 15} заданий"
        
        await query.edit_message_text(message)
        return ConversationHandler.END


async def confirm_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало подтверждения задания сотрудником"""
    user = update.effective_user
    with DatabaseManager() as db:
        employee = db.get_user_by_telegram_id(user.id)
        if not employee:
            await update.message.reply_text("❌ Пользователь не найден.")
            return
        
        tasks = db.get_tasks_by_employee(employee.id, status=TaskStatusEnum.CREATED)
        
        if not tasks:
            await update.message.reply_text("📋 У вас нет новых заданий для подтверждения.")
            return
        
        keyboard = []
        for task in tasks[:10]:
            keyboard.append([InlineKeyboardButton(
                f"Задание №{task.id} - {task.product.name if task.product else 'N/A'}",
                callback_data=f"confirm_task_{task.id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(
            "📋 Выберите задание для подтверждения:",
            reply_markup=reply_markup
        )


async def confirm_task_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение получения задания сотрудником"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[-1])
    
    with DatabaseManager() as db:
        task = db.get_task_by_id(task_id)
        if not task:
            await query.edit_message_text("❌ Задание не найдено.")
            return
        
        if task.status != TaskStatusEnum.CREATED:
            await query.edit_message_text("❌ Это задание уже обработано.")
            return
        
        # Обновляем статус
        db.update_task_status(task_id, TaskStatusEnum.RECEIVED)
        
        # Создаем уведомление для начальника
        manager = db.db.query(User).filter(User.id == task.manager_id).first()
        if manager:
            notification_msg = f"✅ Сотрудник {task.employee.full_name or 'N/A'} подтвердил получение задания №{task.id}"
            db.create_notification(manager.id, task.id, notification_msg)
            
            # Отправляем уведомление начальнику
            try:
                await context.bot.send_message(
                    chat_id=manager.telegram_id,
                    text=f"🔔 {notification_msg}",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления начальнику: {e}")
        
        await query.edit_message_text(f"✅ Задание №{task_id} подтверждено!")


async def report_work_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса отчета о выполненной работе"""
    user = update.effective_user
    with DatabaseManager() as db:
        employee = db.get_user_by_telegram_id(user.id)
        if not employee:
            await update.message.reply_text("❌ Пользователь не найден.")
            return
        
        # Получаем задания, которые можно закрыть (полученные, но не завершенные)
        tasks = db.get_tasks_by_employee(employee.id)
        available_tasks = [t for t in tasks if t.status == TaskStatusEnum.RECEIVED]
        
        if not available_tasks:
            await update.message.reply_text("📋 У вас нет заданий для отчета.")
            return
        
        keyboard = []
        for task in available_tasks[:10]:
            keyboard.append([InlineKeyboardButton(
                f"Задание №{task.id} - План: {task.planned_quantity}",
                callback_data=f"report_{task.id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📝 Выберите задание для отчета:",
            reply_markup=reply_markup
        )
        return SELECTING_TASK_FOR_CONFIRM


async def select_task_for_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор задания для отчета"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[1])
    context.user_data['reporting_task_id'] = task_id
    
    await query.edit_message_text("Введите фактически выполненное количество (число):")
    return ENTERING_ACTUAL_QUANTITY


async def enter_actual_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода фактического количества"""
    try:
        quantity = float(update.message.text.replace(",", "."))
        if quantity < 0:
            await update.message.reply_text("❌ Количество не может быть отрицательным. Введите корректное значение:")
            return ENTERING_ACTUAL_QUANTITY
        
        task_id = context.user_data.get('reporting_task_id')
        if not task_id:
            await update.message.reply_text("❌ Ошибка: задание не выбрано.")
            return ConversationHandler.END
        
        with DatabaseManager() as db:
            task = db.get_task_by_id(task_id)
            if not task:
                await update.message.reply_text("❌ Задание не найдено.")
                return ConversationHandler.END
            
            # Обновляем фактическое количество
            db.update_task_actual_quantity(task_id, quantity)
            
            # Создаем уведомление для начальника
            manager = db.db.query(User).filter(User.id == task.manager_id).first()
            if manager:
                notification_msg = f"📝 Сотрудник {task.employee.full_name or 'N/A'} отчитался по заданию №{task.id}:\n"
                notification_msg += f"План: {task.planned_quantity} | Факт: {quantity}"
                
                db.create_notification(manager.id, task.id, notification_msg)
                
                # Отправляем уведомление начальнику
                try:
                    await context.bot.send_message(
                        chat_id=manager.telegram_id,
                        text=f"🔔 {notification_msg}",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления начальнику: {e}")
            
            await update.message.reply_text(f"✅ Отчет по заданию №{task_id} принят!\nФактическое количество: {quantity}")
            context.user_data.pop('reporting_task_id', None)
            logger.info(f"Задание {task_id} закрыто сотрудником {update.effective_user.id}")
        
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return ENTERING_ACTUAL_QUANTITY


@role_required(['admin', 'manager'])
async def generate_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало генерации отчета для начальника - выбор периода"""
    user = update.effective_user
    with DatabaseManager() as db:
        manager = db.get_user_by_telegram_id(user.id)
        tasks = db.get_tasks_by_manager(manager.id)
        
        if not tasks:
            await update.message.reply_text("📊 У вас нет заданий для отчета.")
            return ConversationHandler.END
        
        # Показываем клавиатуру для выбора периода
        from app.core.utils import get_yesterday_utc3, get_period_dates
        
        yesterday = get_yesterday_utc3()
        week_start, week_end = get_period_dates('week')
        month_start, month_end = get_period_dates('month')
        
        keyboard = [
            [InlineKeyboardButton(f"📅 Вчера ({yesterday.strftime('%d.%m.%Y')})", callback_data="report_period_yesterday")],
            [InlineKeyboardButton(f"📆 Неделя ({week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')})", callback_data="report_period_week")],
            [InlineKeyboardButton(f"📅 Месяц ({month_start.strftime('%d.%m')} - {month_end.strftime('%d.%m.%Y')})", callback_data="report_period_month")],
            [InlineKeyboardButton("📆 Выбрать свой период", callback_data="report_period_custom")],
            [InlineKeyboardButton("❌ Отмена", callback_data="report_period_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 Выберите период для отчета:",
            reply_markup=reply_markup
        )
        return SELECTING_REPORT_PERIOD


@role_required(['admin', 'manager'])
async def select_report_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор формата отчета после выбора периода"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "report_period_cancel":
        await query.edit_message_text("❌ Генерация отчета отменена.")
        return ConversationHandler.END
    
    if query.data == "report_period_custom":
        # Запрашиваем дату начала кастомного периода
        await query.edit_message_text(
            "📆 Выберите кастомный период\n\n"
            "Введите дату начала периода в формате ДД.ММ.ГГГГ\n"
            "Например: 01.01.2026"
        )
        return ENTERING_REPORT_DATE_FROM
    
    period_type = query.data.replace("report_period_", "")  # "yesterday", "week", "month"
    
    # Сохраняем выбранный период в контексте
    context.user_data['report_period'] = period_type
    
    # Показываем клавиатуру для выбора формата
    keyboard = [
        [InlineKeyboardButton("📄 CSV формат", callback_data="report_format_csv")],
        [InlineKeyboardButton("📑 PDF формат", callback_data="report_format_pdf")],
        [InlineKeyboardButton("❌ Отмена", callback_data="report_format_cancel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📊 Выберите формат отчета:",
        reply_markup=reply_markup
    )
    return SELECTING_REPORT_FORMAT


@role_required(['admin', 'manager'])
async def enter_report_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода даты начала кастомного периода"""
    try:
        from app.core.utils import get_yesterday_utc3
        yesterday = get_yesterday_utc3()
        
        # Парсим дату в формате ДД.ММ.ГГГГ
        date_str = update.message.text.strip()
        try:
            date_from = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ\n"
                "Например: 01.01.2026\n\n"
                "Введите дату начала периода:"
            )
            return ENTERING_REPORT_DATE_FROM
        
        # Проверяем, что дата не в будущем (не позже вчера)
        if date_from > yesterday:
            await update.message.reply_text(
                f"❌ Дата начала не может быть позже вчера ({yesterday.strftime('%d.%m.%Y')})\n\n"
                "Введите дату начала периода:"
            )
            return ENTERING_REPORT_DATE_FROM
        
        # Сохраняем дату начала и запрашиваем дату конца
        context.user_data['report_date_from'] = date_from
        await update.message.reply_text(
            f"✅ Дата начала: {date_from.strftime('%d.%m.%Y')}\n\n"
            "Введите дату конца периода в формате ДД.ММ.ГГГГ\n"
            "Например: 10.01.2026"
        )
        return ENTERING_REPORT_DATE_TO
        
    except Exception as e:
        logger.error(f"Ошибка обработки даты начала: {e}")
        await update.message.reply_text(
            "❌ Ошибка обработки даты. Попробуйте еще раз.\n\n"
            "Введите дату начала периода в формате ДД.ММ.ГГГГ:"
        )
        return ENTERING_REPORT_DATE_FROM


@role_required(['admin', 'manager'])
async def enter_report_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода даты конца кастомного периода"""
    try:
        from app.core.utils import get_yesterday_utc3
        yesterday = get_yesterday_utc3()
        
        # Получаем дату начала из контекста
        date_from = context.user_data.get('report_date_from')
        if not date_from:
            await update.message.reply_text("❌ Ошибка: дата начала не сохранена. Начните заново.")
            context.user_data.pop('report_date_from', None)
            return ConversationHandler.END
        
        # Парсим дату конца
        date_str = update.message.text.strip()
        try:
            date_to = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ\n"
                "Например: 10.01.2026\n\n"
                "Введите дату конца периода:"
            )
            return ENTERING_REPORT_DATE_TO
        
        # Проверяем, что дата не в будущем
        if date_to > yesterday:
            await update.message.reply_text(
                f"❌ Дата конца не может быть позже вчера ({yesterday.strftime('%d.%m.%Y')})\n\n"
                "Введите дату конца периода:"
            )
            return ENTERING_REPORT_DATE_TO
        
        # Проверяем, что дата конца не раньше даты начала
        if date_to < date_from:
            await update.message.reply_text(
                f"❌ Дата конца ({date_to.strftime('%d.%m.%Y')}) не может быть раньше даты начала ({date_from.strftime('%d.%m.%Y')})\n\n"
                "Введите дату конца периода:"
            )
            return ENTERING_REPORT_DATE_TO
        
        # Сохраняем даты в контексте как кастомный период
        context.user_data['report_period'] = 'custom'
        context.user_data['report_date_to'] = date_to
        
        # Показываем клавиатуру для выбора формата
        keyboard = [
            [InlineKeyboardButton("📄 CSV формат", callback_data="report_format_csv")],
            [InlineKeyboardButton("📑 PDF формат", callback_data="report_format_pdf")],
            [InlineKeyboardButton("❌ Отмена", callback_data="report_format_cancel")]
        ]
        
        period_text = date_from.strftime('%d.%m.%Y')
        if date_from != date_to:
            period_text = f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"✅ Период выбран: {period_text}\n\n"
            "📊 Выберите формат отчета:",
            reply_markup=reply_markup
        )
        return SELECTING_REPORT_FORMAT
        
    except Exception as e:
        logger.error(f"Ошибка обработки даты конца: {e}")
        await update.message.reply_text(
            "❌ Ошибка обработки даты. Попробуйте еще раз.\n\n"
            "Введите дату конца периода в формате ДД.ММ.ГГГГ:"
        )
        return ENTERING_REPORT_DATE_TO


@role_required(['admin', 'manager'])
async def generate_and_send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка отчета выбранного формата"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "report_format_cancel":
        await query.edit_message_text("❌ Генерация отчета отменена.")
        context.user_data.pop('report_period', None)
        context.user_data.pop('report_date_from', None)
        context.user_data.pop('report_date_to', None)
        return ConversationHandler.END
    
    user = update.effective_user
    format_type = query.data.replace("report_format_", "")  # "csv" или "pdf"
    period_type = context.user_data.get('report_period', 'yesterday')
    
    # Получаем даты периода
    try:
        if period_type == 'custom':
            # Используем сохраненные даты из контекста
            period_from = context.user_data.get('report_date_from')
            period_to = context.user_data.get('report_date_to')
            if not period_from or not period_to:
                await query.edit_message_text("❌ Ошибка: даты периода не сохранены. Начните заново.")
                context.user_data.pop('report_period', None)
                context.user_data.pop('report_date_from', None)
                context.user_data.pop('report_date_to', None)
                return ConversationHandler.END
        else:
            period_from, period_to = get_period_dates(period_type)
    except ValueError as e:
        await query.edit_message_text(f"❌ Ошибка определения периода: {str(e)}")
        context.user_data.pop('report_period', None)
        context.user_data.pop('report_date_from', None)
        context.user_data.pop('report_date_to', None)
        return ConversationHandler.END
    
    # Показываем сообщение о начале генерации
    period_names = {
        'yesterday': 'Вчера',
        'week': 'Неделя',
        'month': 'Месяц'
    }
    period_name = period_names.get(period_type, period_type)
    await query.edit_message_text(f"⏳ Генерирую отчет за период '{period_name}'... Пожалуйста, подождите.")
    
    try:
        with DatabaseManager() as db:
            manager = db.get_user_by_telegram_id(user.id)
            if not manager:
                await query.edit_message_text("❌ Пользователь не найден.")
                context.user_data.pop('report_period', None)
                return ConversationHandler.END
            
            # Получаем задания за выбранный период
            tasks = db.get_tasks_by_manager(manager.id, date_from=period_from, date_to=period_to)
            
            if not tasks:
                period_text = period_from.strftime('%d.%m.%Y')
                if period_from != period_to:
                    period_text = f"{period_from.strftime('%d.%m.%Y')} - {period_to.strftime('%d.%m.%Y')}"
                await query.edit_message_text(f"📊 У вас нет заданий за период {period_text}.")
                context.user_data.pop('report_period', None)
                return ConversationHandler.END
            
            timestamp = get_now_utc3().strftime("%Y%m%d_%H%M%S")
            report_time = get_now_utc3().strftime('%d.%m.%Y %H:%M')
            
            # Формируем название периода для заголовка
            if period_from == period_to:
                period_title = period_from.strftime('%d.%m.%Y')
            else:
                period_title = f"{period_from.strftime('%d.%m.%Y')} - {period_to.strftime('%d.%m.%Y')}"
            
            # Генерируем отчет выбранного формата
            if format_type == "pdf":
                file_path = generate_pdf_report(
                    tasks, 
                    f'reports/report_manager_{manager.id}_{timestamp}.pdf',
                    title='Отчет по заданиям',
                    period_from=period_from,
                    period_to=period_to
                )
                file_caption = f"📑 Отчет по заданиям (PDF)\n\nПериод: {period_title}\nВсего заданий: {len(tasks)}\nСгенерировано: {report_time}"
            else:  # csv
                file_path = generate_csv_report(
                    tasks,
                    f'reports/report_manager_{manager.id}_{timestamp}.csv',
                    period_from=period_from,
                    period_to=period_to
                )
                file_caption = f"📄 Отчет по заданиям (CSV)\n\nПериод: {period_title}\nВсего заданий: {len(tasks)}\nСгенерировано: {report_time}"
            
            # Отправляем файл пользователю
            try:
                with open(file_path, 'rb') as report_file:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=report_file,
                        caption=file_caption,
                        filename=os.path.basename(file_path)
                    )
                
                period_text = period_from.strftime('%d.%m.%Y')
                if period_from != period_to:
                    period_text = f"{period_from.strftime('%d.%m.%Y')} - {period_to.strftime('%d.%m.%Y')}"
                
                await query.edit_message_text(
                    f"✅ Отчет успешно сгенерирован и отправлен!\n\n"
                    f"Период: {period_text}\n"
                    f"Формат: {format_type.upper()}\n"
                    f"Заданий в отчете: {len(tasks)}\n\n"
                    f"💾 Файл доступен в ваших загрузках Telegram."
                )
                logger.info(f"Отчет {file_path} отправлен пользователю {user.id}")
                context.user_data.pop('report_period', None)
                context.user_data.pop('report_date_from', None)
                context.user_data.pop('report_date_to', None)
            except Exception as e:
                logger.error(f"Ошибка отправки файла отчета: {e}")
                await query.edit_message_text(
                    f"❌ Ошибка при отправке файла: {str(e)}\n\n"
                    f"Файл сгенерирован по пути: {file_path}"
                )
                context.user_data.pop('report_period', None)
                context.user_data.pop('report_date_from', None)
                context.user_data.pop('report_date_to', None)
        
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {e}", exc_info=e)
        await query.edit_message_text(f"❌ Ошибка при генерации отчета: {str(e)}")
        context.user_data.pop('report_period', None)
        context.user_data.pop('report_date_from', None)
        context.user_data.pop('report_date_to', None)
        return ConversationHandler.END


async def show_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уведомления"""
    user = update.effective_user
    with DatabaseManager() as db:
        db_user = db.get_user_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("❌ Пользователь не найден.")
            return
        
        notifications = db.get_unread_notifications(db_user.id)
        
        if not notifications:
            await update.message.reply_text("🔔 У вас нет новых уведомлений.")
            return
        
        message = "🔔 Ваши уведомления:\n\n"
        for notif in notifications[:10]:
            message += f"• {notif.message}\n"
            message += f"  <i>{notif.created_at.strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    task_data.pop(update.effective_user.id, None)
    # Очищаем данные отчета, если они есть
    context.user_data.pop('report_period', None)
    context.user_data.pop('report_date_from', None)
    context.user_data.pop('report_date_to', None)
    # Очищаем остальные данные
    context.user_data.clear()
    await update.message.reply_text("❌ Операция отменена.")
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок для логирования и уведомления пользователей"""
    error = context.error
    
    # Обработка конфликта - несколько экземпляров бота запущены одновременно
    if isinstance(error, Conflict):
        logger.critical(
            "CONFLICT: Другой экземпляр бота уже запущен! "
            "Убедитесь, что запущен только один экземпляр бота. "
            "Возможные причины:\n"
            "  1. Развернутая версия бота работает на сервере (Docker контейнер)\n"
            "  2. Бот запущен в другом терминале/окне\n"
            "  3. Другой процесс использует тот же токен бота\n"
            "Решения:\n"
            "  - Для локальной разработки: остановите развернутую версию на сервере\n"
            "  - Или используйте отдельный токен бота для разработки"
        )
        # Для Conflict не отправляем сообщение пользователю - это системная ошибка
        # Останавливаем программу, чтобы не продолжать работу при конфликте
        sys.exit(1)
    
    # Обработка сетевых ошибок и таймаутов
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning(f"Network error occurred: {error}. Retrying...")
        # Для сетевых ошибок также не отправляем сообщение пользователю
        return
    
    # Для остальных ошибок логируем и отправляем сообщение пользователю
    logger.error(f"Exception while handling an update: {error}", exc_info=error)
    
    # Если есть update, пытаемся отправить пользователю сообщение об ошибке
    if update and isinstance(update, Update):
        try:
            message = "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже или обратитесь к администратору."
            if update.effective_message:
                await update.effective_message.reply_text(message)
            elif update.effective_chat:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        except Exception as e:
            logger.error(f"Error while sending error message to user: {e}", exc_info=e)


def main():
    """Главная функция запуска бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в переменных окружения!")
        return
    
    # Инициализация БД
    from app.core.database import init_db, init_sample_data
    init_db()
    # Раскомментируйте следующую строку для создания тестовых данных
    # init_sample_data()
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Обработчик команды /start
    application.add_handler(CommandHandler("start", start))
    
    # Обработчик создания задания (для начальника)
    create_task_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📋 Создать задание$"), create_task_start)],
        states={
            SELECTING_EQUIPMENT: [CallbackQueryHandler(select_equipment)],
            SELECTING_PRODUCT: [CallbackQueryHandler(select_product)],
            ENTERING_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
            SELECTING_EMPLOYEE: [CallbackQueryHandler(select_employee)],
            SELECTING_SHIFT: [CallbackQueryHandler(select_shift)],
            CONFIRMING_TASK: [CallbackQueryHandler(confirm_task)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )
    application.add_handler(create_task_handler)
    
    # Обработчик просмотра заданий начальника с фильтрацией по статусу
    my_tasks_manager_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 Мои задания$"), my_tasks_manager)],
        states={
            SELECTING_STATUS: [CallbackQueryHandler(show_manager_tasks_by_status, pattern="^mgr_status_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )
    application.add_handler(my_tasks_manager_handler)
    
    # Обработчик просмотра заданий сотрудника с фильтрацией по статусу
    my_tasks_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📋 Мои задания$"), my_tasks_employee)],
        states={
            SELECTING_STATUS: [CallbackQueryHandler(show_tasks_by_status, pattern="^status_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )
    application.add_handler(my_tasks_handler)
    
    # Обработчик подтверждения задания сотрудником
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвердить задание$"), confirm_task_start))
    application.add_handler(CallbackQueryHandler(confirm_task_received, pattern="^confirm_task_"))
    
    # Обработчик отчета о работе
    report_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Отчитаться$"), report_work_start)],
        states={
            SELECTING_TASK_FOR_CONFIRM: [CallbackQueryHandler(select_task_for_report, pattern="^report_")],
            ENTERING_ACTUAL_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_actual_quantity)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )
    application.add_handler(report_handler)
    
    # Обработчик генерации отчета с выбором периода и формата
    report_generation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📈 Отчет$"), generate_report_start)],
        states={
            SELECTING_REPORT_PERIOD: [CallbackQueryHandler(select_report_format, pattern="^report_period_")],
            ENTERING_REPORT_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_report_date_from)],
            ENTERING_REPORT_DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_report_date_to)],
            SELECTING_REPORT_FORMAT: [CallbackQueryHandler(generate_and_send_report, pattern="^report_format_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )
    application.add_handler(report_generation_handler)
    
    # Обработчик уведомлений
    application.add_handler(MessageHandler(filters.Regex("^🔔 Уведомления$"), show_notifications))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    logger.info("Бот запущен и готов к работе")
    
    try:
        # Запуск бота
        # run_polling автоматически обрабатывает KeyboardInterrupt и корректно завершает работу
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        # run_polling уже корректно обработал остановку
        logger.info("Бот остановлен пользователем (Ctrl+C)")
        print("\nБот остановлен. Подождите 3-5 секунд перед повторным запуском.")
    except Conflict as e:
        # Этот блок вряд ли будет выполнен, так как error_handler обрабатывает Conflict первым
        # и вызывает sys.exit(1). Оставляем для отладки на случай, если error_handler не сработает.
        logger.critical(
            "КРИТИЧЕСКАЯ ОШИБКА: Другой экземпляр бота уже запущен!\n"
            "Убедитесь, что запущен только один экземпляр бота.\n"
            "Остановите все другие экземпляры перед запуском."
        )
        print("\n" + "="*70)
        print("ОШИБКА: Другой экземпляр бота уже запущен!")
        print("="*70)
        print("\nВозможные причины:")
        print("  • Развернутая версия бота работает на сервере (Docker)")
        print("  • Бот запущен в другом терминале/процессе")
        print("  • Другой процесс использует тот же токен бота")
        print("\nРешения:")
        print("  1. Остановите развернутый бот на сервере:")
        print("     ssh user@server 'docker stop tg_bot_task_manager'")
        print("\n  2. Или проверьте локальные процессы Python:")
        print("     Windows: Get-Process python | Where-Object {$_.Path -like '*bot*'}")
        print("     Linux:   ps aux | grep 'bot.py'")
        print("\n  3. Подождите 5-10 секунд после остановки перед повторным запуском")
        print("="*70 + "\n")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=e)
        raise


if __name__ == '__main__':
    main()
