import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import json
import os
import logging
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Импорт MD3 компонентов
from md3_components import get_md3_css, md3_info_panel, get_md3_table_style, get_md3_chart_colors

# Импорт функции для построения диаграммы Ганта
from gantt_chart import create_gantt_chart

# Импорт функции для парсинга ресурсов
from resource_parser import parse_resources

# Импорт функции для парсинга назначений
from assignment_parser import parse_assignments

# Импорт утилит для работы с MS Project
from msproject_utils import (
    get_namespace, make_tag, find_elements, get_text,
    parse_date, parse_work_hours,
    calculate_available_work_hours, calculate_business_days, calculate_work_capacity,
    find_task_by_name_and_dates
)

# Функция для определения базового пути (для frozen и обычного режима)
def get_base_path():
    """Определяет базовый путь для frozen и обычного режима"""
    import sys
    if getattr(sys, 'frozen', False):
        # Если запущено через PyInstaller
        # Базовый путь - директория, где находится .exe
        if hasattr(sys, 'executable'):
            base_path = os.path.dirname(sys.executable)
        else:
            # Fallback
            base_path = os.path.dirname(os.path.abspath(__file__))
    else:
        # Если запущено напрямую через Python
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return base_path

# Определить базовый путь
BASE_PATH = get_base_path()

# Конфигурация страницы
st.set_page_config(
    page_title="Анализатор управления ресурсами",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Применение MD3 дизайна
st.markdown(get_md3_css(), unsafe_allow_html=True)

# Константа пути к файлу сотрудников (абсолютный путь относительно базовой директории)
EMPLOYEES_FILE = os.path.join(BASE_PATH, "data", "employees.json")

# Функции для работы с JSON-файлом сотрудников
def load_employees_data():
    """Загрузка данных сотрудников и групп из JSON-файла"""
    try:
        # Получить актуальный путь (на случай изменения BASE_PATH)
        employees_file = os.path.join(BASE_PATH, "data", "employees.json")
        
        # Создать папку data/ если её нет
        data_dir = os.path.dirname(employees_file)
        os.makedirs(data_dir, exist_ok=True)
        
        # Если файл существует, загрузить данные
        if os.path.exists(employees_file):
            with open(employees_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'resources': data.get('resources', []),
                    'resource_groups': data.get('resource_groups', {})
                }
        else:
            # Создать файл с пустой структурой
            default_data = {
                'resources': [],
                'resource_groups': {}
            }
            with open(employees_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            return default_data
    except Exception as e:
        st.error(f"Ошибка при загрузке данных сотрудников: {str(e)}")
        return {'resources': [], 'resource_groups': {}}

def save_employees_data(resources, resource_groups):
    """Сохранение данных сотрудников и групп в JSON-файл"""
    try:
        # Получить актуальный путь (на случай изменения BASE_PATH)
        employees_file = os.path.join(BASE_PATH, "data", "employees.json")
        
        # Создать папку data/ если её нет
        data_dir = os.path.dirname(employees_file)
        os.makedirs(data_dir, exist_ok=True)
        
        data = {
            'resources': resources,
            'resource_groups': resource_groups
        }
        
        with open(employees_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Ошибка при сохранении данных сотрудников: {str(e)}")
        return False

def detect_conflicts(existing_resources, new_resources):
    """Обнаружение конфликтов между существующими и новыми сотрудниками (только по имени)"""
    # Конфликты по имени обрабатываются автоматически в merge_resources (пропускаются)
    # Эта функция возвращает пустой список, так как все конфликты по имени разрешаются автоматически
    return []

def merge_resources(existing_resources, new_resources, conflict_resolutions=None):
    """Объединение списков сотрудников с учетом решений по конфликтам (только по имени)"""
    if conflict_resolutions is None:
        conflict_resolutions = {}
    
    # Копируем существующих сотрудников
    merged = existing_resources.copy()
    
    # Словарь для быстрого поиска по имени
    existing_by_name = {r.get('name'): r for r in existing_resources}
    
    for new_resource in new_resources:
        new_name = new_resource.get('name', '')
        
        # Проверяем, есть ли конфликт по имени
        has_name_conflict = new_name in existing_by_name
        
        # Проверяем, есть ли решение для этого конфликта
        conflict_key = new_name
        resolution = conflict_resolutions.get(conflict_key)
        
        if resolution == 'skip':
            # Пропустить - не добавлять (оставить из файла)
            continue
        elif resolution == 'update':
            # Обновить существующего по имени
            if has_name_conflict:
                index = merged.index(existing_by_name[new_name])
                merged[index] = new_resource.copy()
        elif resolution == 'add_new':
            # Добавить как нового сотрудника
            merged.append(new_resource.copy())
        else:
            # По умолчанию: если имя совпадает, пропускаем (оставляем из файла)
            # Если имя не совпадает, добавляем новый ресурс
            if not has_name_conflict:
                merged.append(new_resource.copy())
    
    return merged

# MS Project XML Parser
class MSProjectParser:
    """Парсер для XML-файлов MS Project (.xml, .mspdi)"""
    
    def __init__(self, file_content):
        self.file_content = file_content
        self.tasks = []
        self.resources = []
        self.assignments = []
        self.project_name = None
    
    @staticmethod
    def clean_xml_content(xml_bytes):
        """
        Удаляет недопустимые символы из XML-контента.
        XML 1.0 допускает только определённые символы:
        - 0x09 (tab), 0x0A (LF), 0x0D (CR)
        - 0x20-0xD7FF, 0xE000-0xFFFD, 0x10000-0x10FFFF
        """
        # Декодируем в строку
        try:
            xml_str = xml_bytes.decode('utf-8')
        except:
            xml_str = xml_bytes.decode('utf-8', errors='ignore')
        
        # Функция для проверки допустимости символа
        def is_valid_xml_char(c):
            codepoint = ord(c)
            return (
                codepoint == 0x09 or
                codepoint == 0x0A or
                codepoint == 0x0D or
                (0x20 <= codepoint <= 0xD7FF) or
                (0xE000 <= codepoint <= 0xFFFD) or
                (0x10000 <= codepoint <= 0x10FFFF)
            )
        
        # Фильтруем недопустимые символы
        cleaned_str = ''.join(c for c in xml_str if is_valid_xml_char(c))
        
        # Возвращаем обратно в байты
        return cleaned_str.encode('utf-8')
        
    def parse(self):
        """Парсинг XML-файла MS Project"""
        try:
            # Очищаем логи перед парсингом
            if 'parsing_logs' in st.session_state:
                st.session_state.parsing_logs.clear()
            
            # Очищаем XML от недопустимых символов
            cleaned_content = self.clean_xml_content(self.file_content)
            
            tree = etree.parse(io.BytesIO(cleaned_content))
            root = tree.getroot()
            
            # Получение namespace
            namespace = get_namespace(root)
            
            # Парсинг названия проекта
            self.project_name = get_text(root, make_tag('Name', namespace), namespace, default='Неизвестный проект')
            
            # Парсинг ресурсов
            st.info("🔍 Начинаю парсинг ресурсов...")
            # Добавляем тестовое логирование
            resource_logger.info("=== НАЧАЛО ПАРСИНГА РЕСУРСОВ ===")
            self.resources = parse_resources(root, namespace, filter_inactive=True)
            resource_logger.info(f"=== ПАРСИНГ РЕСУРСОВ ЗАВЕРШЕН: найдено {len(self.resources)} ресурсов ===")
            st.success(f"✓ Найдено ресурсов: {len(self.resources)}")
            
            # Парсинг задач
            st.info("🔍 Начинаю парсинг задач...")
            self.tasks = self._parse_tasks(root, namespace)
            st.success(f"✓ Найдено задач: {len(self.tasks)}")
            
            # Парсинг назначений
            st.info("🔍 Начинаю парсинг назначений...")
            # Добавляем тестовое логирование
            assignment_logger.info("=== НАЧАЛО ПАРСИНГА НАЗНАЧЕНИЙ ===")
            self.assignments = parse_assignments(root, namespace, self.resources, self.tasks)
            assignment_logger.info(f"=== ПАРСИНГ НАЗНАЧЕНИЙ ЗАВЕРШЕН: найдено {len(self.assignments)} назначений ===")
            st.success(f"✓ Найдено назначений: {len(self.assignments)}")
            
            # Проверяем, что логи собраны
            if 'parsing_logs' in st.session_state:
                st.info(f"📝 Собрано логов: {len(st.session_state.parsing_logs)} записей")
            
            return True
        except Exception as e:
            st.error(f"Ошибка при парсинге файла MS Project: {str(e)}")
            return False
    
    # Метод _parse_resources перенесен в модуль resource_parser
    # Используется функция parse_resources из resource_parser.py
    
    def _parse_tasks(self, root, namespace):
        """Parse task information including dependencies"""
        tasks = []
        task_elements = find_elements(root, 'Task', namespace)
        
        for task in task_elements:
            task_id = get_text(task, make_tag('UID', namespace), namespace)
            name = get_text(task, make_tag('Name', namespace), namespace)
            
            # Если имя пустое, сгенерировать автоматически
            if not name and task_id:
                name = f"Задача #{task_id}"
            
            # Если нет task_id, пропустить задачу (не можем сгенерировать имя)
            if not task_id:
                continue
            
            # Парсинг зависимостей задач (PredecessorLink)
            predecessors = []
            pred_links = find_elements(task, 'PredecessorLink', namespace)
            for pred in pred_links:
                pred_uid = get_text(pred, make_tag('PredecessorUID', namespace), namespace)
                if pred_uid:
                    predecessors.append(pred_uid)
            
            tasks.append({
                'id': str(task_id),  # Сохраняем для отладки и зависимостей
                'name': name,
                'start': get_text(task, make_tag('Start', namespace), namespace),
                'finish': get_text(task, make_tag('Finish', namespace), namespace),
                'duration': get_text(task, make_tag('Duration', namespace), namespace),
                'work': get_text(task, make_tag('Work', namespace), namespace),
                'predecessors': [str(p) for p in predecessors]  # Преобразуем в строки для единообразия
            })
        
        return tasks
    
    # Метод _parse_assignments перенесен в модуль assignment_parser
    # Используется функция parse_assignments из assignment_parser.py
    
    def get_resource_workload_data(self, date_range_start=None, date_range_end=None):
        """
        Calculate workload data for each resource.
        
        Args:
            date_range_start: Начало анализируемого периода (datetime.date or None)
            date_range_end: Конец анализируемого периода (datetime.date or None)
        """
        workload_data = []
        
        # Calculate project timeframe for capacity calculation
        project_start = None
        project_end = None
        
        for task in self.tasks:
            if task['start']:
                task_start = self._parse_date(task['start'])
                if task_start and (project_start is None or task_start < project_start):
                    project_start = task_start
            
            if task['finish']:
                task_end = self._parse_date(task['finish'])
                if task_end and (project_end is None or task_end > project_end):
                    project_end = task_end
        
        # Использовать выбранный диапазон или весь проект
        if date_range_start and date_range_end:
            # Конвертировать date в datetime для вычислений
            from datetime import datetime as dt_class
            range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
            range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        else:
            range_start_dt = project_start
            range_end_dt = project_end
        
        # Calculate total available work hours for the selected range
        # Используем утилиту для расчета доступных рабочих часов
        available_work_hours_base = calculate_available_work_hours(
            date_range_start if date_range_start else project_start,
            date_range_end if date_range_end else project_end,
            default_hours=160
        )
        
        for resource in self.resources:
            # Get all assignments for this resource (по имени)
            resource_name = resource.get('name', '')
            resource_assignments = [a for a in self.assignments if a.get('resource_name') == resource_name]
            
            # Calculate total work hours (only within date range)
            total_work_hours = 0
            task_details = []
            
            for assignment in resource_assignments:
                # Get task info по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    self.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                
                if task and task.get('start') and task.get('finish'):
                    task_start = self._parse_date(task['start'])
                    task_end = self._parse_date(task['finish'])
                    
                    if task_start and task_end and range_start_dt and range_end_dt:
                        # Проверить пересечение задачи с диапазоном
                        overlap_days, proportion = self.compute_overlap(
                            task_start, task_end, range_start_dt, range_end_dt
                        )
                        
                        if proportion > 0:
                            # Учитывать только часы попадающие в диапазон
                            total_task_hours = self._parse_work_hours(assignment['work'])
                            hours_in_range = total_task_hours * proportion
                            total_work_hours += hours_in_range
                            
                            task_details.append({
                                'task_id': task.get('id', 'N/A'),  # Только для отладки
                                'task_name': task['name'],
                                'work_hours': hours_in_range,
                                'total_hours': total_task_hours,
                                'proportion': proportion,
                                'start': task.get('start', 'N/A'),
                                'finish': task.get('finish', 'N/A')
                            })
                    else:
                        # Если нет диапазона, учитывать всю задачу
                        work_hours = self._parse_work_hours(assignment['work'])
                        total_work_hours += work_hours
                        task_details.append({
                            'task_id': task.get('id', 'N/A'),  # Только для отладки
                            'task_name': task['name'],
                            'work_hours': work_hours,
                            'start': task.get('start', 'N/A'),
                            'finish': task.get('finish', 'N/A')
                        })
            
            # Calculate capacity based on resource MaxUnits and available work hours
            max_units = float(resource.get('max_units', 1.0))
            # Capacity = available work hours × max_units
            max_capacity = available_work_hours_base * max_units
            workload_percentage = (total_work_hours / max_capacity) * 100 if max_capacity > 0 else 0
            
            # Calculate project weeks for display purposes
            project_weeks = available_work_hours_base / 40
            
            workload_data.append({
                'resource_name': resource['name'],
                'total_work_hours': total_work_hours,
                'max_capacity': max_capacity,
                'workload_percentage': workload_percentage,
                'task_count': len(resource_assignments),
                'tasks': task_details,
                'project_weeks': project_weeks
            })
        
        return workload_data
    
    def _parse_date(self, date_string):
        """Parse date string to datetime object (использует утилиту)"""
        return parse_date(date_string)
    
    def _parse_work_hours(self, work_string):
        """Parse work hours from MS Project ISO-8601 duration format (использует утилиту)"""
        return parse_work_hours(work_string)
    
    def get_timeline_workload(self, date_range_start=None, date_range_end=None):
        """
        Рассчитать временную загрузку ресурсов по неделям.
        
        Args:
            date_range_start: Начало анализируемого периода (datetime.date or None)
            date_range_end: Конец анализируемого периода (datetime.date or None)
        """
        timeline_data = {}
        
        # Определить временные границы проекта
        project_start = None
        project_end = None
        
        for task in self.tasks:
            if task['start']:
                task_start = self._parse_date(task['start'])
                if task_start and (project_start is None or task_start < project_start):
                    project_start = task_start
            
            if task['finish']:
                task_end = self._parse_date(task['finish'])
                if task_end and (project_end is None or task_end > project_end):
                    project_end = task_end
        
        # Использовать выбранный диапазон или весь проект
        if date_range_start and date_range_end:
            from datetime import datetime as dt_class
            range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
            range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        else:
            range_start_dt = project_start
            range_end_dt = project_end
        
        if not range_start_dt or not range_end_dt:
            return {}
        
        # Создать недельные периоды только для выбранного диапазона
        current_date = range_start_dt
        weeks = []
        while current_date <= range_end_dt:
            week_end = current_date + timedelta(days=6)
            weeks.append({
                'start': current_date,
                'end': min(week_end, range_end_dt),
                'label': f"{current_date.strftime('%d.%m')} - {min(week_end, range_end_dt).strftime('%d.%m')}"
            })
            current_date = week_end + timedelta(days=1)
        
        # Для каждого ресурса рассчитать загрузку по неделям
        for resource in self.resources:
            resource_name = resource.get('name', '')
            resource_assignments = [a for a in self.assignments if a.get('resource_name') == resource_name]
            weekly_loads = []
            
            for week in weeks:
                week_hours = 0
                
                for assignment in resource_assignments:
                    # Поиск задачи по комбинации имени и дат
                    task = find_task_by_name_and_dates(
                        self.tasks,
                        assignment.get('task_name'),
                        assignment.get('task_start'),
                        assignment.get('task_finish')
                    )
                    if task and task.get('start') and task.get('finish'):
                        task_start = self._parse_date(task['start'])
                        task_end = self._parse_date(task['finish'])
                        
                        if task_start and task_end:
                            # Проверить пересечение задачи с неделей
                            overlap_start = max(task_start, week['start'])
                            overlap_end = min(task_end, week['end'])
                            
                            if overlap_start <= overlap_end:
                                # Рассчитать долю работы в этой неделе
                                task_total_hours = self._parse_work_hours(assignment['work'])
                                task_duration_days = (task_end - task_start).days + 1
                                overlap_days = (overlap_end - overlap_start).days + 1
                                
                                if task_duration_days > 0:
                                    proportion = overlap_days / task_duration_days
                                    week_hours += task_total_hours * proportion
                
                # Ёмкость за неделю: 5 рабочих дней × 8 часов × max_units
                max_units = float(resource.get('max_units', 1.0))
                week_capacity = 40 * max_units
                week_percentage = (week_hours / week_capacity) * 100 if week_capacity > 0 else 0
                
                weekly_loads.append({
                    'week': week['label'],
                    'week_start': week['start'],
                    'week_end': week['end'],
                    'hours': week_hours,
                    'capacity': week_capacity,
                    'percentage': week_percentage
                })
            
            timeline_data[resource['name']] = weekly_loads
        
        return timeline_data
    
    def get_project_dates(self):
        """Получить минимальную и максимальную даты проекта"""
        project_start = None
        project_end = None
        
        for task in self.tasks:
            if task['start']:
                task_start = self._parse_date(task['start'])
                if task_start and (project_start is None or task_start < project_start):
                    project_start = task_start
            
            if task['finish']:
                task_end = self._parse_date(task['finish'])
                if task_end and (project_end is None or task_end > project_end):
                    project_end = task_end
        
        return project_start, project_end
    
    @staticmethod
    def compute_overlap(task_start, task_end, range_start, range_end):
        """
        Рассчитать пересечение задачи с временным диапазоном.
        Возвращает (overlap_days, proportion) где:
        - overlap_days: количество дней пересечения
        - proportion: доля задачи попадающая в диапазон (0.0-1.0)
        """
        # Проверить что задача пересекается с диапазоном
        if task_end < range_start or task_start > range_end:
            return 0, 0.0
        
        # Найти пересечение
        overlap_start = max(task_start, range_start)
        overlap_end = min(task_end, range_end)
        
        # Рассчитать дни
        overlap_days = (overlap_end - overlap_start).days + 1
        task_total_days = (task_end - task_start).days + 1
        
        # Рассчитать пропорцию
        proportion = overlap_days / task_total_days if task_total_days > 0 else 0.0
        
        return max(0, overlap_days), max(0.0, min(1.0, proportion))

# Multi-Project Parser
class MultiProjectParser:
    """Парсер для объединения данных из нескольких файлов MS Project"""
    
    def __init__(self, parsers):
        """
        Инициализация с списком парсеров
        
        Args:
            parsers: список объектов MSProjectParser
        """
        self.parsers = parsers if parsers else []
        self._merged_resources = None
        self._merged_tasks = None
        self._merged_assignments = None
    
    def get_merged_resources(self):
        """Объединяет ресурсы из всех парсеров (автоматически по ID/имени)"""
        if self._merged_resources is not None:
            return self._merged_resources
        
        merged = {}
        
        for parser in self.parsers:
            for resource in parser.resources:
                resource_name = resource.get('name', '')
                
                if not resource_name:
                    continue
                
                # Объединяем только по имени (парсим только по имени)
                if resource_name in merged:
                    # Ресурс с таким именем уже есть - обновляем max_units
                    existing = merged[resource_name]
                    existing_max = float(existing.get('max_units', 1.0))
                    new_max = float(resource.get('max_units', 1.0))
                    if new_max > existing_max:
                        existing['max_units'] = str(new_max)
                    continue
                
                # Новый ресурс - добавляем
                merged[resource_name] = resource.copy()
        
        self._merged_resources = list(merged.values())
        return self._merged_resources
    
    @property
    def resources(self):
        """Объединенные ресурсы из всех парсеров"""
        return self.get_merged_resources()
    
    @resources.setter
    def resources(self, value):
        """Установить ресурсы для всех парсеров"""
        # Обновить ресурсы во всех парсерах
        for parser in self.parsers:
            parser.resources = value
        # Обновить кэш объединенных ресурсов
        self._merged_resources = value
    
    @property
    def tasks(self):
        """Объединенные задачи из всех парсеров"""
        if self._merged_tasks is not None:
            return self._merged_tasks
        
        merged_tasks = []
        for parser in self.parsers:
            merged_tasks.extend(parser.tasks)
        
        self._merged_tasks = merged_tasks
        return self._merged_tasks
    
    @property
    def assignments(self):
        """Объединенные назначения из всех парсеров"""
        if self._merged_assignments is not None:
            return self._merged_assignments
        
        merged_assignments = []
        for parser in self.parsers:
            merged_assignments.extend(parser.assignments)
        
        self._merged_assignments = merged_assignments
        return self._merged_assignments
    
    def get_project_dates(self):
        """Получить минимальную и максимальную даты из всех проектов"""
        project_start = None
        project_end = None
        
        for parser in self.parsers:
            start, end = parser.get_project_dates()
            if start and (project_start is None or start < project_start):
                project_start = start
            if end and (project_end is None or end > project_end):
                project_end = end
        
        return project_start, project_end
    
    def get_resource_workload_data(self, date_range_start=None, date_range_end=None):
        """Агрегирует нагрузку из всех проектов"""
        # Получить данные из всех парсеров
        all_workload_data = []
        for parser in self.parsers:
            workload_data = parser.get_resource_workload_data(date_range_start, date_range_end)
            all_workload_data.extend(workload_data)
        
        # Агрегировать данные по ресурсам
        aggregated = {}
        merged_resources = self.get_merged_resources()
        
        # Инициализировать агрегированные данные для всех ресурсов
        for resource in merged_resources:
            resource_name = resource['name']
            max_units = float(resource.get('max_units', 1.0))
            
            # Рассчитать доступную емкость (используем утилиту)
            if date_range_start and date_range_end:
                range_start = date_range_start
                range_end = date_range_end
            else:
                project_start, project_end = self.get_project_dates()
                range_start = project_start
                range_end = project_end
            
            available_work_hours_base = calculate_available_work_hours(
                range_start,
                range_end,
                default_hours=160
            )
            
            max_capacity = available_work_hours_base * max_units
            project_weeks = available_work_hours_base / 40
            
            aggregated[resource_name] = {
                'resource_name': resource_name,
                'total_work_hours': 0,
                'max_capacity': max_capacity,
                'workload_percentage': 0,
                'task_count': 0,
                'tasks': [],
                'project_weeks': project_weeks
            }
        
        # Агрегировать данные из всех проектов
        for item in all_workload_data:
            resource_name = item['resource_name']
            if resource_name in aggregated:
                aggregated[resource_name]['total_work_hours'] += item['total_work_hours']
                aggregated[resource_name]['task_count'] += item['task_count']
                aggregated[resource_name]['tasks'].extend(item['tasks'])
        
        # Пересчитать проценты нагрузки
        for resource_name, data in aggregated.items():
            if data['max_capacity'] > 0:
                data['workload_percentage'] = (data['total_work_hours'] / data['max_capacity']) * 100
        
        return list(aggregated.values())
    
    def get_timeline_workload(self, date_range_start=None, date_range_end=None):
        """Объединяет временные данные из всех проектов"""
        # Получить данные из всех парсеров
        all_timeline_data = {}
        for parser in self.parsers:
            timeline_data = parser.get_timeline_workload(date_range_start, date_range_end)
            for resource_name, weekly_loads in timeline_data.items():
                if resource_name not in all_timeline_data:
                    all_timeline_data[resource_name] = {}
                
                # Объединить недельные данные
                for week_data in weekly_loads:
                    week_key = week_data['week']
                    if week_key not in all_timeline_data[resource_name]:
                        all_timeline_data[resource_name][week_key] = {
                            'week': week_key,
                            'week_start': week_data['week_start'],
                            'week_end': week_data['week_end'],
                            'hours': 0,
                            'capacity': week_data['capacity'],
                            'percentage': 0
                        }
                    
                    all_timeline_data[resource_name][week_key]['hours'] += week_data['hours']
        
        # Пересчитать проценты для объединенных данных
        result = {}
        for resource_name, weeks_dict in all_timeline_data.items():
            weekly_loads = []
            for week_key in sorted(weeks_dict.keys(), key=lambda k: weeks_dict[k]['week_start']):
                week_data = weeks_dict[week_key]
                if week_data['capacity'] > 0:
                    week_data['percentage'] = (week_data['hours'] / week_data['capacity']) * 100
                weekly_loads.append(week_data)
            result[resource_name] = weekly_loads
        
        return result
    
    def _parse_date(self, date_string):
        """Парсинг дат (использует утилиту)"""
        return parse_date(date_string)
    
    def _parse_work_hours(self, work_string):
        """Парсинг часов работы (использует утилиту)"""
        return parse_work_hours(work_string)
    
    def get_resource_id_mapping(self):
        """Создает маппинг resource_id -> resource_name для всех парсеров (для обратной совместимости)"""
        # Больше не используется, так как парсим только по имени
        return {}
    
    def get_assignments_for_resource(self, resource_name):
        """Получить все назначения для ресурса по имени (парсим только по имени)"""
        return [a for a in self.assignments if a.get('resource_name') == resource_name]

# Analysis functions
def analyze_workload(workload_data):
    """Analyze workload and categorize resources"""
    analysis = {
        'overloaded': [],
        'optimal': [],
        'underutilized': []
    }
    
    for item in workload_data:
        percentage = item['workload_percentage']
        if percentage > 100:
            analysis['overloaded'].append(item)
        elif percentage >= 70:
            analysis['optimal'].append(item)
        else:
            analysis['underutilized'].append(item)
    
    return analysis

def check_task_dependencies(task_id, new_start, new_end, parser, task_dict):
    """
    Проверяет, что сдвиг задачи не нарушает зависимости с предшественниками
    
    Returns:
        (is_valid, blocking_tasks) - можно ли сдвинуть и список блокирующих задач
    """
    task = task_dict.get(task_id)
    if not task or not task.get('predecessors'):
        return True, []  # Нет зависимостей - можно сдвигать
    
    blocking_tasks = []
    
    # Проверить все предшественники
    for pred_id in task['predecessors']:
        pred_task = task_dict.get(pred_id)
        if not pred_task or not pred_task.get('finish'):
            continue
        
        pred_end = parser._parse_date(pred_task['finish'])
        if not pred_end:
            continue
        
        # Проверить, что предшественник завершился до начала задачи
        # (простая зависимость Finish-to-Start)
        if new_start < pred_end:
            blocking_tasks.append({
                'id': pred_id,
                'name': pred_task.get('name', 'Unknown'),
                'finish': pred_end.strftime('%Y-%m-%d'),
                'required_start': pred_end.strftime('%Y-%m-%d')
            })
    
    return len(blocking_tasks) == 0, blocking_tasks


def calculate_precise_improvement(task_info, source_week, target_week, shift_days, 
                                   task_start, task_end, task_hours, weeks_with_dates, weekly_loads):
    """
    Точный расчет улучшения с учетом частичных перекрытий задачи с неделями
    
    Returns:
        (improvement_percentage, hours_removed, hours_added, is_valid)
    """
    new_start = task_start + timedelta(days=shift_days)
    new_end = task_end + timedelta(days=shift_days)
    
    # Точный расчет: сколько часов задачи было в исходной неделе
    source_overlap_start = max(task_start, source_week['start'])
    source_overlap_end = min(task_end, source_week['end'])
    
    if source_overlap_start > source_overlap_end:
        return 0, 0, 0, False
    
    task_duration_days = (task_end - task_start).days + 1
    source_overlap_days = (source_overlap_end - source_overlap_start).days + 1
    source_proportion = source_overlap_days / task_duration_days if task_duration_days > 0 else 0
    hours_removed_from_source = task_hours * source_proportion
    
    # Точный расчет: сколько часов задачи будет в целевой неделе
    target_overlap_start = max(new_start, target_week['start'])
    target_overlap_end = min(new_end, target_week['end'])
    
    if target_overlap_start > target_overlap_end:
        return 0, 0, 0, False
    
    target_overlap_days = (target_overlap_end - target_overlap_start).days + 1
    target_proportion = target_overlap_days / task_duration_days if task_duration_days > 0 else 0
    hours_added_to_target = task_hours * target_proportion
    
    # Рассчитать новую загрузку
    new_source_hours = source_week['hours'] - hours_removed_from_source
    new_source_percentage = (new_source_hours / source_week['capacity']) * 100 if source_week['capacity'] > 0 else 0
    
    new_target_hours = target_week['hours'] + hours_added_to_target
    new_target_percentage = (new_target_hours / target_week['capacity']) * 100 if target_week['capacity'] > 0 else 0
    
    # Проверка валидности
    is_valid = (new_source_percentage < source_week['percentage'] and 
                new_target_percentage <= 100)
    
    improvement = source_week['percentage'] - new_source_percentage if is_valid else 0
    
    return improvement, hours_removed_from_source, hours_added_to_target, is_valid


def binary_search_optimal_shift(task_info, source_week, target_week_idx, weekly_loads, 
                                  weeks_with_dates, parser, task_dict, max_shift, week_idx):
    """
    Бинарный поиск оптимального сдвига вместо линейного перебора
    
    Returns:
        (best_shift, best_improvement) or (None, 0)
    """
    task = task_info['task']
    task_start = task_info['start']
    task_end = task_info['end']
    task_hours = task_info['hours']
    
    if target_week_idx >= len(weekly_loads) or target_week_idx == week_idx:
        return None, 0
    
    target_week = weekly_loads[target_week_idx]
    
    # Проверка зависимостей для граничного случая
    new_start_max = task_start + timedelta(days=max_shift)
    new_end_max = task_end + timedelta(days=max_shift)
    is_valid_max, _ = check_task_dependencies(task['id'], new_start_max, new_end_max, parser, task_dict)
    
    if not is_valid_max:
        # Если максимальный сдвиг нарушает зависимости, ищем меньший
        left, right = 1, max_shift
        best_shift = None
        best_improvement = 0
        
        while left <= right:
            mid = (left + right) // 2
            new_start = task_start + timedelta(days=mid)
            new_end = task_end + timedelta(days=mid)
            
            is_valid, _ = check_task_dependencies(task['id'], new_start, new_end, parser, task_dict)
            improvement, _, _, valid_shift = calculate_precise_improvement(
                task_info, source_week, target_week, mid,
                task_start, task_end, task_hours, weeks_with_dates, weekly_loads
            )
            
            if is_valid and valid_shift and improvement > best_improvement:
                best_shift = mid
                best_improvement = improvement
                # Пробуем больший сдвиг
                left = mid + 1
            else:
                # Меньший сдвиг
                right = mid - 1
        
        return best_shift, best_improvement
    
    # Если зависимости не нарушаются, ищем оптимальный сдвиг бинарным поиском
    left, right = 1, max_shift
    best_shift = None
    best_improvement = 0
    
    while left <= right:
        mid = (left + right) // 2
        
        improvement, _, _, is_valid = calculate_precise_improvement(
            task_info, source_week, target_week, mid,
            task_start, task_end, task_hours, weeks_with_dates, weekly_loads
        )
        
        if is_valid and improvement > best_improvement:
            best_shift = mid
            best_improvement = improvement
        
        # Если улучшение растет, пробуем больший сдвиг, иначе меньший
        if mid < max_shift:
            next_improvement, _, _, next_valid = calculate_precise_improvement(
                task_info, source_week, target_week, mid + 1,
                task_start, task_end, task_hours, weeks_with_dates, weekly_loads
            )
            if next_valid and next_improvement > improvement:
                left = mid + 1
            else:
                right = mid - 1
        else:
            break
    
    return best_shift, best_improvement


def optimize_with_task_shifting(parser, settings, date_range_start=None, date_range_end=None, selected_resources=None):
    """
    Оптимизация распределения с смещением задач во времени
    
    Args:
        parser: MSProjectParser instance
        settings: Настройки оптимизации
            {
                'max_shift_days': int,  # Максимальное смещение задач в днях
                'target_load': float,   # Целевая загрузка (70-100%)
                'mode': 'balance'       # Режим: 'balance' или 'minimize_peaks'
            }
        date_range_start: Начало анализируемого периода (datetime.date or None)
        date_range_end: Конец анализируемого периода (datetime.date or None)
        selected_resources: Список выбранных ресурсов для оптимизации (list or None)
    """
    max_shift = settings.get('max_shift_days', 14)
    target_load = settings.get('target_load', 85)
    mode = settings.get('mode', 'balance')
    
    # Получить временную загрузку с учётом диапазона
    timeline_data = parser.get_timeline_workload(date_range_start, date_range_end)
    # Создать task_dict по ID только для зависимостей (не для связывания назначений)
    task_dict = {t['id']: t for t in parser.tasks}
    
    # Найти перегруженные периоды для каждого ресурса
    optimization_suggestions = []
    
    for resource_name, weekly_loads in timeline_data.items():
        # Фильтрация по выбранным ресурсам
        if selected_resources and resource_name not in selected_resources:
            continue
        # Найти перегруженные и недозагруженные недели
        overloaded_weeks = {}
        underloaded_weeks = {}
        
        for i, week_data in enumerate(weekly_loads):
            if week_data['percentage'] > 100:
                overloaded_weeks[i] = week_data
            elif week_data['percentage'] < target_load:
                underloaded_weeks[i] = week_data
        
        if not overloaded_weeks:
            continue
        
        # Найти задачи этого ресурса
        resource = next((r for r in parser.resources if r['name'] == resource_name), None)
        if not resource:
            continue
        
        # Для MultiProjectParser использовать специальный метод
        if isinstance(parser, MultiProjectParser):
            resource_assignments = parser.get_assignments_for_resource(resource_name)
        else:
            resource_assignments = [a for a in parser.assignments if a.get('resource_name') == resource_name]
        
        # Построить карту недель для быстрого поиска (один раз на ресурс)
        # КРИТИЧНО: Использовать тот же диапазон что и в get_timeline_workload()
        project_start = None
        project_end = None
        for task_item in parser.tasks:
            if task_item['start']:
                ts = parser._parse_date(task_item['start'])
                if ts and (project_start is None or ts < project_start):
                    project_start = ts
            if task_item['finish']:
                te = parser._parse_date(task_item['finish'])
                if te and (project_end is None or te > project_end):
                    project_end = te
        
        # Использовать выбранный диапазон или весь проект
        if date_range_start and date_range_end:
            from datetime import datetime as dt_class
            range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
            range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        else:
            range_start_dt = project_start
            range_end_dt = project_end
        
        if not range_start_dt or not range_end_dt:
            continue
            
        current_date = range_start_dt
        weeks_with_dates = []
        while current_date <= range_end_dt:
            week_end = current_date + timedelta(days=6)
            weeks_with_dates.append({
                'start': current_date,
                'end': min(week_end, range_end_dt),
                'index': len(weeks_with_dates)
            })
            current_date = week_end + timedelta(days=1)
        
        # Для каждой перегруженной недели найти задачи, которые можно сдвинуть
        for week_idx, week_data in overloaded_weeks.items():
            excess_hours = week_data['hours'] - week_data['capacity']
            
            # Получить временные границы текущей недели
            if week_idx >= len(weeks_with_dates):
                continue
            current_week_info = weeks_with_dates[week_idx]
            week_start = current_week_info['start']
            week_end = current_week_info['end']
            
            # Найти задачи, пересекающиеся с этой неделей
            tasks_in_week = []
            for assignment in resource_assignments:
                # Поиск задачи по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    parser.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                if not task or not task.get('start') or not task.get('finish'):
                    continue
                
                task_start = parser._parse_date(task['start'])
                task_end = parser._parse_date(task['finish'])
                if not task_start or not task_end:
                    continue
                
                # КРИТИЧНО: Проверить, что задача пересекается с текущей неделей
                if task_end < week_start or task_start > week_end:
                    continue  # Задача не пересекается с этой неделей
                
                task_hours = parser._parse_work_hours(assignment['work'])
                tasks_in_week.append({
                    'task': task,
                    'assignment': assignment,
                    'start': task_start,
                    'end': task_end,
                    'hours': task_hours
                })
            
            # Приоритизация задач: сортировка по влиянию на перегрузку
            # Влияние = (часы задачи в неделе) * (процент перегрузки недели)
            def calculate_task_impact(task_info):
                task_start = task_info['start']
                task_end = task_info['end']
                
                # Найти долю задачи в перегруженной неделе
                overlap_start = max(task_start, week_start)
                overlap_end = min(task_end, week_end)
                
                if overlap_start > overlap_end:
                    return 0
                
                task_duration_days = (task_end - task_start).days + 1
                overlap_days = (overlap_end - overlap_start).days + 1
                proportion = overlap_days / task_duration_days if task_duration_days > 0 else 0
                hours_in_week = task_info['hours'] * proportion
                
                # Влияние = часы в неделе * уровень перегрузки
                impact = hours_in_week * week_data['percentage']
                return impact
            
            # Сортировка по влиянию (наибольшее влияние первым)
            tasks_in_week.sort(key=calculate_task_impact, reverse=True)
            
            # Попробовать сдвинуть задачи в недозагруженные периоды
            for task_info in tasks_in_week:
                task = task_info['task']
                task_start = task_info['start']
                task_end = task_info['end']
                task_hours = task_info['hours']
                
                best_shift = None
                best_improvement = 0
                best_target_week_idx = None
                
                # Найти подходящие целевые недели (недозагруженные)
                # Принимаем все недозагруженные недели как кандидаты
                # Бинарный поиск проверит, может ли задача достичь недели с любым сдвигом до max_shift
                candidate_target_weeks = []
                for i, target_week in enumerate(weekly_loads):
                    if i != week_idx and target_week['percentage'] < target_load:
                        candidate_target_weeks.append(i)
                
                # Для каждой целевой недели найти оптимальный сдвиг бинарным поиском
                for target_week_idx in candidate_target_weeks:
                    if target_week_idx >= len(weekly_loads):
                        continue
                    
                    target_week = weekly_loads[target_week_idx]
                    
                    # Бинарный поиск оптимального сдвига
                    shift, improvement = binary_search_optimal_shift(
                        task_info, week_data, target_week_idx, weekly_loads,
                        weeks_with_dates, parser, task_dict, max_shift, week_idx
                    )
                    
                    if shift and improvement > best_improvement:
                        # Проверить зависимости для найденного сдвига
                        new_start_check = task_start + timedelta(days=shift)
                        new_end_check = task_end + timedelta(days=shift)
                        is_valid, blocking = check_task_dependencies(
                            task['id'], new_start_check, new_end_check, parser, task_dict
                        )
                        
                        if is_valid:
                            best_improvement = improvement
                            best_shift = shift
                            best_target_week_idx = target_week_idx
                        elif shift > 1:
                            # Если зависимости нарушены, попробовать меньший сдвиг
                            for smaller_shift in range(1, shift):
                                new_start_small = task_start + timedelta(days=smaller_shift)
                                new_end_small = task_end + timedelta(days=smaller_shift)
                                is_valid_small, _ = check_task_dependencies(
                                    task['id'], new_start_small, new_end_small, parser, task_dict
                                )
                                if is_valid_small:
                                    improvement_small, _, _, valid = calculate_precise_improvement(
                                        task_info, week_data, target_week, smaller_shift,
                                        task_start, task_end, task_hours, weeks_with_dates, weekly_loads
                                    )
                                    if valid and improvement_small > best_improvement:
                                        best_improvement = improvement_small
                                        best_shift = smaller_shift
                                        best_target_week_idx = target_week_idx
                                        break
                
                # Если нашли хороший сдвиг, добавляем рекомендацию
                if best_shift and best_target_week_idx is not None:
                    new_start = task_start + timedelta(days=best_shift)
                    new_end = task_end + timedelta(days=best_shift)
                    
                    # Точный расчет для финальной рекомендации
                    target_week_final = weekly_loads[best_target_week_idx]
                    _, hours_removed, hours_added, _ = calculate_precise_improvement(
                        task_info, week_data, target_week_final, best_shift,
                        task_start, task_end, task_hours, weeks_with_dates, weekly_loads
                    )
                    
                    optimization_suggestions.append({
                        'type': 'shift_task',
                        'resource': resource_name,
                        'task_name': task['name'],
                        'task_hours': task_hours,
                        'original_start': task_start.strftime('%Y-%m-%d'),
                        'original_end': task_end.strftime('%Y-%m-%d'),
                        'suggested_start': new_start.strftime('%Y-%m-%d'),
                        'suggested_end': new_end.strftime('%Y-%m-%d'),
                        'shift_days': best_shift,
                        'improvement': f'{best_improvement:.1f}%',
                        'hours_freed': f'{hours_removed:.1f}',
                        'hours_added': f'{hours_added:.1f}',
                        'reason': f'Снизить перегрузку на {hours_removed:.1f}ч в неделю {week_data["week"]} (точный расчет)',
                        'priority': 'Высокий' if week_data['percentage'] > 120 else 'Средний'
                    })
                    
                    # Для режима balance берём только одну задачу на неделю
                    if mode == 'balance':
                        break
    
    return optimization_suggestions

def generate_recommendations(analysis):
    """Generate actionable recommendations based on actual resource capacity"""
    recommendations = []
    
    overloaded = analysis['overloaded']
    underutilized = analysis['underutilized']
    
    if overloaded and underutilized:
        for overloaded_resource in overloaded:
            for underutilized_resource in underutilized:
                # Calculate excess hours based on actual capacity
                overload_percentage = overloaded_resource['workload_percentage'] - 100
                excess_hours = (overload_percentage / 100) * overloaded_resource['max_capacity']
                
                # Calculate available capacity
                underutil_percentage = 100 - underutilized_resource['workload_percentage']
                available_capacity = (underutil_percentage / 100) * underutilized_resource['max_capacity']
                
                if available_capacity > 0:
                    hours_to_move = min(excess_hours, available_capacity)
                    recommendations.append({
                        'type': 'Reassign Tasks',
                        'from': overloaded_resource['resource_name'],
                        'to': underutilized_resource['resource_name'],
                        'hours': hours_to_move,
                        'priority': 'High' if overloaded_resource['workload_percentage'] > 120 else 'Medium'
                    })
    
    elif overloaded and not underutilized:
        for resource in overloaded:
            overload_percentage = resource['workload_percentage'] - 100
            excess_hours = (overload_percentage / 100) * resource['max_capacity']
            recommendations.append({
                'type': 'Hire Additional Resources',
                'resource': resource['resource_name'],
                'reason': f'Overloaded by {resource["workload_percentage"] - 100:.1f}% ({excess_hours:.1f} hours)',
                'priority': 'High' if resource['workload_percentage'] > 120 else 'Medium'
            })
    
    elif underutilized:
        for resource in underutilized:
            underutil_percentage = 100 - resource['workload_percentage']
            available_hours = (underutil_percentage / 100) * resource['max_capacity']
            recommendations.append({
                'type': 'Increase Utilization',
                'resource': resource['resource_name'],
                'available_capacity': f'{100 - resource["workload_percentage"]:.1f}% ({available_hours:.1f} hours)',
                'priority': 'Low'
            })
    
    return recommendations

def export_to_csv(workload_df, analysis, parser=None, timeline_data=None, optimization_results=None, date_start=None, date_end=None, business_days=None, capacity=None):
    """
    Экспорт детального анализа в CSV с несколькими секциями:
    1. Период анализа (если указан)
    2. Сводка по ресурсам (всегда)
    3. Детализация задач по ресурсам (если есть parser)
    4. Временное распределение по неделям (если есть timeline_data)
    5. Предложения по оптимизации (если есть optimization_results)
    """
    import re
    
    def remove_emojis(text):
        """Удалить emoji из текста для совместимости с cp1251"""
        if isinstance(text, str):
            # Удалить emoji и другие символы Unicode за пределами cp1251
            return re.sub(r'[^\u0000-\u04FF]', '', text)
        return text
    
    csv_buffer = io.StringIO()
    
    # Период анализа (если указан)
    if date_start and date_end:
        period_str = f"{date_start.strftime('%d.%m.%Y')} - {date_end.strftime('%d.%m.%Y')}"
        csv_buffer.write(f"ПЕРИОД АНАЛИЗА: {period_str}\n")
        if business_days is not None:
            csv_buffer.write(f"Рабочие дни: {business_days}\n")
        if capacity is not None:
            csv_buffer.write(f"Рабочая ёмкость на человека: {capacity} ч.\n")
        csv_buffer.write("\n")
    
    # Очистить DataFrame от emoji перед экспортом
    df_clean = workload_df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            df_clean[col] = df_clean[col].apply(remove_emojis)
    
    # Секция 1: Сводка по ресурсам
    csv_buffer.write("СВОДКА ПО РЕСУРСАМ\n")
    df_clean.to_csv(csv_buffer, index=False)
    csv_buffer.write("\n\n")
    
    # Секция 2: Детализация задач по ресурсам
    if parser:
        csv_buffer.write("ДЕТАЛИЗАЦИЯ ЗАДАЧ ПО РЕСУРСАМ\n")
        csv_buffer.write("Ресурс,ID задачи,Название задачи,Начало,Конец,Трудоёмкость (часы)\n")
        
        for resource in parser.resources:
            resource_name = resource['name']
            # Для MultiProjectParser использовать специальный метод
            if isinstance(parser, MultiProjectParser):
                resource_assignments = parser.get_assignments_for_resource(resource_name)
            else:
                resource_assignments = [a for a in parser.assignments if a.get('resource_name') == resource_name]
            
            for assignment in resource_assignments:
                # Поиск задачи по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    parser.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                if task:
                    task_id = task.get('id', 'N/A')  # Только для отладки
                    task_name = task.get('name', 'Без названия')
                    task_start = task.get('start', '')
                    task_finish = task.get('finish', '')
                    task_hours = parser._parse_work_hours(assignment['work'])
                    
                    csv_buffer.write(f'"{resource_name}","{task_id}","{task_name}","{task_start}","{task_finish}",{task_hours:.2f}\n')
        csv_buffer.write("\n\n")
    
    # Секция 3: Временное распределение по неделям
    if timeline_data:
        csv_buffer.write("ВРЕМЕННОЕ РАСПРЕДЕЛЕНИЕ ПО НЕДЕЛЯМ\n")
        csv_buffer.write("Ресурс,Неделя начало,Неделя конец,Часы,Ёмкость,Процент загрузки\n")
        
        for resource_name, weekly_loads in timeline_data.items():
            for week_data in weekly_loads:
                week_start = week_data['week_start'].strftime('%Y-%m-%d')
                week_end = week_data['week_end'].strftime('%Y-%m-%d')
                hours = week_data['hours']
                capacity = week_data['capacity']
                percentage = week_data['percentage']
                
                csv_buffer.write(f'"{resource_name}",{week_start},{week_end},{hours:.2f},{capacity:.2f},{percentage:.2f}\n')
        csv_buffer.write("\n\n")
    
    # Секция 4: Предложения по оптимизации
    if optimization_results:
        csv_buffer.write("ПРЕДЛОЖЕНИЯ ПО ОПТИМИЗАЦИИ\n")
        csv_buffer.write("Ресурс,Задача,Оригинальные даты,Предлагаемые даты,Смещение (дни),Улучшение,Причина,Приоритет\n")
        
        for suggestion in optimization_results:
            resource = suggestion.get('resource', '')
            task_name = suggestion.get('task_name', '')
            orig_dates = f"{suggestion.get('original_start', '')} - {suggestion.get('original_end', '')}"
            sugg_dates = f"{suggestion.get('suggested_start', '')} - {suggestion.get('suggested_end', '')}"
            shift_days = suggestion.get('shift_days', '')
            improvement = suggestion.get('improvement', '')
            reason = suggestion.get('reason', '')
            priority = suggestion.get('priority', '')
            
            csv_buffer.write(f'"{resource}","{task_name}","{orig_dates}","{sugg_dates}",{shift_days},"{improvement}","{reason}","{priority}"\n')
        csv_buffer.write("\n")
    
    # Кодировка cp1251 для совместимости с Excel
    return csv_buffer.getvalue().encode('cp1251')

def export_to_pdf(workload_df, analysis, recommendations, parser=None, timeline_data=None, optimization_results=None, date_start=None, date_end=None, business_days=None, capacity=None):
    """
    Экспорт детального анализа в PDF с несколькими секциями:
    1. Период анализа (если указан)
    2. Сводка и таблица рабочей нагрузки (всегда)
    3. Детализация задач по ресурсам (если есть parser)
    4. Временное распределение по неделям (если есть timeline_data)
    5. Предложения по оптимизации (если есть optimization_results)
    """
    # Регистрация шрифтов DejaVu для поддержки кириллицы
    dejavu_available = False
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        dejavu_available = True
    except:
        pass  # Если шрифты не найдены, используем стандартные Helvetica
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Выбрать шрифты в зависимости от доступности DejaVu
    if dejavu_available:
        normal_font = 'DejaVuSans'
        bold_font = 'DejaVuSans-Bold'
        # Обновление стандартных стилей для использования DejaVu Sans
        for style_name in styles.byName:
            style = styles[style_name]
            style.fontName = normal_font
    else:
        normal_font = 'Helvetica'
        bold_font = 'Helvetica-Bold'
    
    # Заголовок
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        fontName=bold_font,
        textColor=colors.HexColor('#0078D4'),
        spaceAfter=30
    )
    elements.append(Paragraph("Отчёт по анализу рабочей нагрузки ресурсов", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Период анализа (если указан)
    if date_start and date_end:
        period_str = f"{date_start.strftime('%d.%m.%Y')} - {date_end.strftime('%d.%m.%Y')}"
        period_text = f"<b>Период анализа:</b> {period_str}"
        if business_days is not None:
            period_text += f"<br/><b>Рабочие дни:</b> {business_days}"
        if capacity is not None:
            period_text += f"<br/><b>Рабочая ёмкость на человека:</b> {capacity} ч."
        elements.append(Paragraph(period_text, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
    
    # Сводка
    summary_text = f"""
    <b>Сводка анализа</b><br/>
    Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
    Всего ресурсов: {len(workload_df)}<br/>
    Перегружено: {len(analysis['overloaded'])}<br/>
    Оптимально: {len(analysis['optimal'])}<br/>
    Недоиспользуется: {len(analysis['underutilized'])}
    """
    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Таблица рабочей нагрузки
    # Проверить наличие столбцов
    has_period_hours = 'Рабочие часы за период' in workload_df.columns
    has_percentage_col = 'Нагрузка %' in workload_df.columns
    has_hours_col = 'Загрузка (часы)' in workload_df.columns
    
    # Заголовки таблицы
    if has_period_hours:
        if has_hours_col:
            table_data = [['Ресурс', 'Выделено', 'Ёмкость', 'Часы за период', 'Загрузка (ч)', 'Задачи', 'Статус']]
        else:
            table_data = [['Ресурс', 'Выделено', 'Ёмкость', 'Часы за период', 'Нагрузка %', 'Задачи', 'Статус']]
    else:
        if has_hours_col:
            table_data = [['Ресурс', 'Выделено', 'Ёмкость', 'Загрузка (ч)', 'Задачи', 'Статус']]
        else:
            table_data = [['Ресурс', 'Выделено', 'Ёмкость', 'Нагрузка %', 'Задачи', 'Статус']]
    
    for _, row in workload_df.iterrows():
        # Вычислить процент для определения статуса
        if has_percentage_col:
            percentage = row['Нагрузка %']
        elif has_hours_col and row['Ёмкость часов'] > 0:
            percentage = (row['Загрузка (часы)'] / row['Ёмкость часов']) * 100
        else:
            percentage = 0
        
        status = 'Перегружен' if percentage > 100 else ('Оптимально' if percentage >= 70 else 'Недоиспользуется')
        
        # Формировать строку в зависимости от наличия колонок
        if has_period_hours:
            if has_hours_col:
                table_data.append([
                    row['Имя ресурса'],
                    f"{row['Выделено часов']:.1f}ч",
                    f"{row['Ёмкость часов']:.1f}ч",
                    f"{row['Рабочие часы за период']:.1f}ч",
                    f"{row['Загрузка (часы)']:.1f}ч",
                    str(row['Кол-во задач']),
                    status
                ])
            else:
                table_data.append([
                    row['Имя ресурса'],
                    f"{row['Выделено часов']:.1f}ч",
                    f"{row['Ёмкость часов']:.1f}ч",
                    f"{row['Рабочие часы за период']:.1f}ч",
                    f"{row['Нагрузка %']:.1f}%",
                    str(row['Кол-во задач']),
                    status
                ])
        else:
            if has_hours_col:
                table_data.append([
                    row['Имя ресурса'],
                    f"{row['Выделено часов']:.1f}ч",
                    f"{row['Ёмкость часов']:.1f}ч",
                    f"{row['Загрузка (часы)']:.1f}ч",
                    str(row['Кол-во задач']),
                    status
                ])
            else:
                table_data.append([
                    row['Имя ресурса'],
                    f"{row['Выделено часов']:.1f}ч",
                    f"{row['Ёмкость часов']:.1f}ч",
                    f"{row['Нагрузка %']:.1f}%",
                    str(row['Кол-во задач']),
                    status
                ])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTNAME', (0, 1), (-1, -1), normal_font),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Рекомендации
    if recommendations:
        heading_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontName=bold_font
        )
        elements.append(Paragraph("<b>Рекомендации</b>", heading_style))
        for i, rec in enumerate(recommendations[:10], 1):
            if rec['type'] == 'Reassign Tasks':
                rec_text = f"{i}. Перераспределить задачи - Перенести {rec['hours']:.1f}ч от {rec['from']} к {rec['to']}"
            elif rec['type'] == 'Hire Additional Resources':
                rec_text = f"{i}. Нанять дополнительные ресурсы для {rec['resource']}: {rec['reason']}"
            else:
                rec_text = f"{i}. Увеличить использование {rec['resource']}: {rec['available_capacity']}"
            elements.append(Paragraph(rec_text, styles['Normal']))
    
    # Секция: Детализация задач по ресурсам
    if parser:
        elements.append(Spacer(1, 0.5*inch))
        heading_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontName=bold_font
        )
        elements.append(Paragraph("<b>Детализация задач по ресурсам</b>", heading_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Создать таблицу задач (ограничить до 50 задач для читаемости)
        task_table_data = [['Ресурс', 'Задача', 'Начало', 'Конец', 'Часы']]
        task_count = 0
        max_tasks = 50
        
        for resource in parser.resources[:10]:  # Ограничить до 10 ресурсов
            resource_name = resource['name']
            # Для MultiProjectParser использовать специальный метод
            if isinstance(parser, MultiProjectParser):
                resource_assignments = parser.get_assignments_for_resource(resource_name)
            else:
                resource_assignments = [a for a in parser.assignments if a.get('resource_name') == resource_name]
            
            for assignment in resource_assignments[:5]:  # До 5 задач на ресурс
                if task_count >= max_tasks:
                    break
                # Поиск задачи по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    parser.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                if task:
                    task_name = task.get('name', 'Без названия')[:30]  # Обрезать длинные имена
                    task_start = task.get('start', '')[:10] if task.get('start') else ''
                    task_finish = task.get('finish', '')[:10] if task.get('finish') else ''
                    task_hours = parser._parse_work_hours(assignment['work'])
                    
                    task_table_data.append([
                        resource_name[:20],
                        task_name,
                        task_start,
                        task_finish,
                        f"{task_hours:.1f}ч"
                    ])
                    task_count += 1
            
            if task_count >= max_tasks:
                break
        
        if len(task_table_data) > 1:
            task_table = Table(task_table_data, colWidths=[1.2*inch, 2.5*inch, 1*inch, 1*inch, 0.8*inch])
            task_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), bold_font),
                ('FONTNAME', (0, 1), (-1, -1), normal_font),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(task_table)
    
    # Секция: Временное распределение по неделям
    if timeline_data:
        elements.append(Spacer(1, 0.5*inch))
        heading_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontName=bold_font
        )
        elements.append(Paragraph("<b>Временное распределение по неделям</b>", heading_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Создать таблицу недель (ограничить для читаемости)
        week_table_data = [['Ресурс', 'Период', 'Часы', 'Ёмкость', 'Загрузка %']]
        week_count = 0
        max_weeks = 40
        
        for resource_name, weekly_loads in list(timeline_data.items())[:5]:  # До 5 ресурсов
            for week_data in weekly_loads[:8]:  # До 8 недель на ресурс
                if week_count >= max_weeks:
                    break
                week_label = week_data['week']
                hours = week_data['hours']
                capacity = week_data['capacity']
                percentage = week_data['percentage']
                
                week_table_data.append([
                    resource_name[:20],
                    week_label,
                    f"{hours:.1f}ч",
                    f"{capacity:.1f}ч",
                    f"{percentage:.1f}%"
                ])
                week_count += 1
            
            if week_count >= max_weeks:
                break
        
        if len(week_table_data) > 1:
            week_table = Table(week_table_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
            week_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), bold_font),
                ('FONTNAME', (0, 1), (-1, -1), normal_font),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(week_table)
    
    # Секция: Детальные предложения по оптимизации
    if optimization_results:
        elements.append(Spacer(1, 0.5*inch))
        heading_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontName=bold_font
        )
        elements.append(Paragraph("<b>Детальные предложения по оптимизации</b>", heading_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Создать таблицу оптимизации
        opt_table_data = [['Ресурс', 'Задача', 'Смещение', 'Улучшение', 'Причина']]
        
        for i, suggestion in enumerate(optimization_results[:20]):  # До 20 предложений
            resource = suggestion.get('resource', '')[:15]
            task_name = suggestion.get('task_name', '')[:20]
            shift_info = f"{suggestion.get('shift_days', '')} дн."
            improvement = suggestion.get('improvement', '')
            reason = suggestion.get('reason', '')[:40]
            
            opt_table_data.append([
                resource,
                task_name,
                shift_info,
                improvement,
                reason
            ])
        
        if len(opt_table_data) > 1:
            opt_table = Table(opt_table_data, colWidths=[1*inch, 1.5*inch, 0.8*inch, 0.8*inch, 2.4*inch])
            opt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), bold_font),
                ('FONTNAME', (0, 1), (-1, -1), normal_font),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(opt_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Функции calculate_business_days и calculate_work_capacity перенесены в msproject_utils
# Импортируются из утилит в начале файла

def calculate_actual_hours_per_resource(parser, date_start, date_end):
    """Рассчитывает фактические рабочие часы для каждого ресурса за указанный период"""
    if not parser:
        return {}
    
    resource_hours = {}
    
    # Работать с MultiProjectParser или обычным MSProjectParser
    if isinstance(parser, MultiProjectParser):
        # Для MultiProjectParser агрегировать данные из всех парсеров
        for single_parser in parser.parsers:
            single_hours = calculate_actual_hours_per_resource(single_parser, date_start, date_end)
            for resource_name, hours in single_hours.items():
                if resource_name not in resource_hours:
                    resource_hours[resource_name] = 0
                resource_hours[resource_name] += hours
        return resource_hours
    
    # Получить все задачи из parser
    for task in parser.tasks:
        task_start_raw = task.get('start')
        task_end_raw = task.get('finish')
        
        if not task_start_raw or not task_end_raw:
            continue
        
        # Преобразовать в date если это datetime
        if isinstance(task_start_raw, str):
            try:
                task_start = datetime.fromisoformat(task_start_raw).date()
            except:
                continue
        elif isinstance(task_start_raw, datetime):
            task_start = task_start_raw.date()
        else:
            task_start = task_start_raw
            
        if isinstance(task_end_raw, str):
            try:
                task_end = datetime.fromisoformat(task_end_raw).date()
            except:
                continue
        elif isinstance(task_end_raw, datetime):
            task_end = task_end_raw.date()
        else:
            task_end = task_end_raw
        
        # Проверить пересечение с выбранным диапазоном
        if task_end < date_start or task_start > date_end:
            continue
        
        # Пересечение диапазонов
        overlap_start = max(task_start, date_start)
        overlap_end = min(task_end, date_end)
        
        # Найти все назначения для этой задачи по комбинации имени и дат
        task_name = task.get('name', '')
        task_start_str = task.get('start', '')
        task_finish_str = task.get('finish', '')
        
        task_assignments = [
            a for a in parser.assignments
            if a.get('task_name') == task_name
            and a.get('task_start') == task_start_str
            and a.get('task_finish') == task_finish_str
        ]
        
        for assignment in task_assignments:
            # Используем имя ресурса напрямую (парсим только по имени)
            resource_name = assignment.get('resource_name')
            if not resource_name:
                continue
            
            work_hours = parser._parse_work_hours(assignment.get('work', '0'))
            
            # Пропорция задачи в выбранном диапазоне
            task_duration_days = (task_end - task_start).days + 1
            overlap_duration_days = (overlap_end - overlap_start).days + 1
            
            if task_duration_days > 0:
                proportion = overlap_duration_days / task_duration_days
                hours_in_range = work_hours * proportion
            else:
                hours_in_range = work_hours
            
            # Суммировать часы для ресурса
            if resource_name not in resource_hours:
                resource_hours[resource_name] = 0
            resource_hours[resource_name] += hours_in_range
    
    return resource_hours

# Initialize session state
if 'workload_data' not in st.session_state:
    st.session_state.workload_data = None
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'parser' not in st.session_state:
    st.session_state.parser = None
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = None
if 'timeline_data' not in st.session_state:
    st.session_state.timeline_data = None
if 'resource_replacements' not in st.session_state:
    st.session_state.resource_replacements = {}
if 'date_range_start' not in st.session_state:
    st.session_state.date_range_start = None
if 'date_range_end' not in st.session_state:
    st.session_state.date_range_end = None
if 'resource_groups' not in st.session_state or 'saved_resources' not in st.session_state:
    # Загрузить данные из файла при первом запуске
    employees_data = load_employees_data()
    if 'resource_groups' not in st.session_state:
        st.session_state.resource_groups = employees_data.get('resource_groups', {})
    if 'saved_resources' not in st.session_state:
        st.session_state.saved_resources = employees_data.get('resources', [])
if 'conflict_resolutions' not in st.session_state:
    st.session_state.conflict_resolutions = {}
if 'pending_conflicts' not in st.session_state:
    st.session_state.pending_conflicts = []
if 'display_mode' not in st.session_state:
    st.session_state.display_mode = 'percentage'  # По умолчанию проценты
if 'uploaded_file_contents' not in st.session_state:
    st.session_state.uploaded_file_contents = {}
if 'uploaded_file_names' not in st.session_state:
    st.session_state.uploaded_file_names = []

# Настройка логирования для Streamlit (после инициализации session_state)
class StreamlitHandler(logging.Handler):
    """Обработчик логирования для вывода в Streamlit"""
    def __init__(self, logs_list):
        super().__init__()
        self.logs_list = logs_list
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            if self.logs_list is not None:
                self.logs_list.append(log_entry)
                # Ограничиваем количество логов (последние 1000)
                if len(self.logs_list) > 1000:
                    self.logs_list[:] = self.logs_list[-1000:]
        except Exception:
            pass  # Игнорируем ошибки при логировании

# Инициализация логирования после session_state
if 'parsing_logs' not in st.session_state:
    st.session_state.parsing_logs = []

# Создаем handler только если session_state инициализирован
streamlit_handler = StreamlitHandler(st.session_state.parsing_logs)
streamlit_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
streamlit_handler.setLevel(logging.DEBUG)

# Настраиваем логирование для модулей парсинга
resource_logger = logging.getLogger('resource_parser')
assignment_logger = logging.getLogger('assignment_parser')

# Удаляем старые handlers, если есть
for handler in resource_logger.handlers[:]:
    resource_logger.removeHandler(handler)
for handler in assignment_logger.handlers[:]:
    assignment_logger.removeHandler(handler)

resource_logger.setLevel(logging.DEBUG)
assignment_logger.setLevel(logging.DEBUG)
resource_logger.addHandler(streamlit_handler)
assignment_logger.addHandler(streamlit_handler)
resource_logger.propagate = False  # Отключаем распространение, чтобы избежать дублирования
assignment_logger.propagate = False

# Main application
def main():
    # Заголовок
    st.markdown("""
        <h1 style='color: #0078D4; margin-bottom: 10px;'>📊 Анализатор управления ресурсами</h1>
        <p style='color: #323130; font-size: 16px; margin-bottom: 30px;'>
            Анализируйте файлы Microsoft Project для выявления дисбаланса рабочей нагрузки и оптимизации распределения ресурсов
        </p>
    """, unsafe_allow_html=True)
    
    # Боковая панель
    with st.sidebar:
        # Переключатель отображения загрузки
        st.markdown("###  Отображение загрузки")
        display_options = {
            'percentage': 'В процентах',
            'hours': 'В часах'
        }
        
        selected_display = st.radio(
            "Выберите формат:",
            options=list(display_options.keys()),
            format_func=lambda x: display_options[x],
            key='display_selector',
            label_visibility='collapsed'
        )
        
        # Если режим отображения изменился, обновляем session_state и перезагружаем
        if selected_display != st.session_state.display_mode:
            st.session_state.display_mode = selected_display
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### 📁 Загрузка файлов MS Project")
        st.markdown("Поддерживаемые форматы: .xml, .mspdi")
        st.info("💡 Чтобы экспортировать .mpp в XML: в MS Project выберите Файл → Сохранить как → выберите Формат XML (*.xml)")
        
        uploaded_files = st.file_uploader(
            "Выберите файлы",
            type=['xml', 'mspdi'],
            accept_multiple_files=True,
            help="Загрузите один или несколько XML-файлов Microsoft Project для анализа"
        )
        
        # Сохранить содержимое файлов в session_state сразу после загрузки
        # Это предотвратит ошибку 400 при rerun()
        if uploaded_files is not None and len(uploaded_files) > 0:
            # Проверить, изменились ли загруженные файлы
            current_file_names = [f.name for f in uploaded_files]
            saved_file_names = st.session_state.get('uploaded_file_names', [])
            
            if current_file_names != saved_file_names:
                # Файлы изменились - сохранить их содержимое
                st.session_state.uploaded_file_contents = {}
                st.session_state.uploaded_file_names = []
                
                for uploaded_file in uploaded_files:
                    try:
                        file_content = uploaded_file.getvalue()
                        st.session_state.uploaded_file_contents[uploaded_file.name] = file_content
                        st.session_state.uploaded_file_names.append(uploaded_file.name)
                    except (AttributeError, RuntimeError, OSError) as e:
                        # Ошибка 400 или файл недоступен - попробуем использовать сохраненное содержимое
                        if uploaded_file.name in st.session_state.get('uploaded_file_contents', {}):
                            # Файл уже сохранен, используем его
                            continue
                        else:
                            st.warning(f"⚠️ Не удалось сохранить файл {uploaded_file.name}: {str(e)}. Попробуйте загрузить файл снова.")
                    except Exception as e:
                        st.warning(f"⚠️ Не удалось сохранить файл {uploaded_file.name}: {str(e)}")
        
        # Проверить наличие загруженных файлов
        has_files = (uploaded_files is not None and len(uploaded_files) > 0) or \
                    (st.session_state.get('uploaded_file_names') is not None and len(st.session_state.get('uploaded_file_names', [])) > 0)
        
        if has_files:
            # Использовать сохраненные имена файлов, если uploaded_files недоступен
            if uploaded_files is not None and len(uploaded_files) > 0:
                file_count = len(uploaded_files)
                file_names = [f.name for f in uploaded_files]
            else:
                file_names = st.session_state.get('uploaded_file_names', [])
                file_count = len(file_names)
            
            if file_count == 1:
                st.success(f"✓ {file_names[0]} загружен")
            else:
                st.success(f"✓ Загружено файлов: {file_count}")
                with st.expander("📋 Список загруженных файлов", expanded=False):
                    for i, name in enumerate(file_names, 1):
                        st.text(f"{i}. {name}")
            
            button_text = "🔄 Анализировать файл" if file_count == 1 else f"🔄 Анализировать {file_count} файлов"
            if st.button(button_text, use_container_width=True):
                with st.spinner(f"Анализ {file_count} файл(ов) MS Project..."):
                    # Использовать сохраненное содержимое файлов из session_state
                    file_contents = st.session_state.get('uploaded_file_contents', {})
                    file_names_to_process = st.session_state.get('uploaded_file_names', [])
                    
                    # Если файлы еще доступны напрямую, попробовать использовать их
                    if uploaded_files is not None and len(uploaded_files) > 0:
                        # Обновить сохраненное содержимое на случай, если файлы изменились
                        for uploaded_file in uploaded_files:
                            try:
                                file_content = uploaded_file.getvalue()
                                file_contents[uploaded_file.name] = file_content
                                if uploaded_file.name not in file_names_to_process:
                                    file_names_to_process.append(uploaded_file.name)
                            except (AttributeError, RuntimeError, OSError) as e:
                                # Ошибка 400 или файл недоступен - используем сохраненное содержимое
                                if uploaded_file.name not in file_contents:
                                    # Если файл не сохранен, добавим его в список неудачных
                                    if uploaded_file.name not in file_names_to_process:
                                        file_names_to_process.append(uploaded_file.name)
                            except Exception as e:
                                # Если не удалось получить напрямую, используем сохраненное
                                if uploaded_file.name not in file_contents:
                                    if uploaded_file.name not in file_names_to_process:
                                        file_names_to_process.append(uploaded_file.name)
                    
                    if not file_contents or len(file_names_to_process) == 0:
                        st.error("Нет файлов для анализа. Пожалуйста, загрузите файлы снова.")
                    else:
                        # Создать парсер для каждого файла
                        parsers = []
                        all_resources = []
                        failed_files = []
                        parser_to_file_name = {}  # Маппинг parser -> file_name
                        
                        for file_name in file_names_to_process:
                            try:
                                # Получить содержимое из session_state
                                file_content = file_contents.get(file_name)
                                
                                if file_content is None:
                                    failed_files.append(f"{file_name}: файл недоступен")
                                    continue
                                
                                parser = MSProjectParser(file_content)
                                if parser.parse():
                                    parsers.append(parser)
                                    all_resources.extend(parser.resources)
                                    # Сохранить маппинг parser -> file_name
                                    parser_to_file_name[parser] = file_name
                                    
                                    # Показываем логи парсинга
                                    if 'parsing_logs' in st.session_state and st.session_state.parsing_logs:
                                        with st.expander(f"📋 Логи парсинга: {file_name}", expanded=True):
                                            log_text = "\n".join(st.session_state.parsing_logs)
                                            if log_text:
                                                st.code(log_text, language='text')
                                                st.caption(f"Всего записей в логе: {len(st.session_state.parsing_logs)}")
                                            else:
                                                st.info("Логи пусты")
                                else:
                                    failed_files.append(file_name)
                            except Exception as e:
                                failed_files.append(f"{file_name}: {str(e)}")
                        
                        if failed_files:
                            st.warning(f"⚠️ Не удалось проанализировать {len(failed_files)} файл(ов): {', '.join(failed_files)}")
                        
                        if parsers:
                            # Сохранить маппинг parser -> file_name в session_state
                            st.session_state.parser_to_file_name = parser_to_file_name
                            
                            # Обнаружение конфликтов между сотрудниками из всех XML и сохраненными
                            conflicts = detect_conflicts(st.session_state.saved_resources, all_resources)
                            
                            if conflicts:
                                # Сохранить конфликты для отображения в UI
                                st.session_state.pending_conflicts = conflicts
                                # Создать временный MultiProjectParser для хранения данных
                                multi_parser = MultiProjectParser(parsers)
                                st.session_state.parser = multi_parser
                                st.warning(f"⚠️ Обнаружено {len(conflicts)} конфликт(ов) при объединении сотрудников. Разрешите их ниже.")
                            else:
                                # Нет конфликтов - объединяем автоматически
                                merged_resources = merge_resources(
                                    st.session_state.saved_resources,
                                    all_resources,
                                    st.session_state.conflict_resolutions
                                )
                                st.session_state.saved_resources = merged_resources
                                
                                # Обновить ресурсы во всех парсерах
                                for parser in parsers:
                                    parser.resources = merged_resources
                                
                                # Сохранить в файл
                                save_employees_data(
                                    st.session_state.saved_resources,
                                    st.session_state.resource_groups
                                )
                                
                                # Создать MultiProjectParser из всех парсеров
                                multi_parser = MultiProjectParser(parsers)
                                st.session_state.parser = multi_parser
                                
                                # Инициализировать даты проекта на основе текущей даты
                                today = datetime.now().date()
                                
                                # Получить даты проекта для ограничения
                                project_start, project_end = multi_parser.get_project_dates()
                                
                                # Начало: текущая дата - 7 дней, округленная до понедельника
                                start_candidate = today - timedelta(days=7)
                                days_since_monday = start_candidate.weekday()
                                default_start = start_candidate - timedelta(days=days_since_monday)
                                
                                # Конец: текущая дата + 14 дней, округленная до пятницы
                                end_candidate = today + timedelta(days=14)
                                days_until_friday = (4 - end_candidate.weekday()) % 7
                                default_end = end_candidate + timedelta(days=days_until_friday)
                                
                                # Ограничить даты в пределах проекта
                                if project_start and project_end:
                                    project_start_date = project_start.date()
                                    project_end_date = project_end.date()
                                    default_start = max(default_start, project_start_date)
                                    default_start = min(default_start, project_end_date)
                                    default_end = max(default_end, project_start_date)
                                    default_end = min(default_end, project_end_date)
                                
                                st.session_state.date_range_start = default_start
                                st.session_state.date_range_end = default_end
                                # Рассчитать данные с учетом выбранного диапазона
                                st.session_state.workload_data = multi_parser.get_resource_workload_data(
                                    st.session_state.date_range_start,
                                    st.session_state.date_range_end
                                )
                                st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                                
                                if file_count == 1:
                                    st.success("✓ Файл успешно проанализирован!")
                                else:
                                    st.success(f"✓ {len(parsers)} файл(ов) успешно проанализировано!")
                                st.rerun()
                        else:
                            st.error("Не удалось проанализировать ни один файл")
        
        # UI для разрешения конфликтов при парсинге XML
        if st.session_state.pending_conflicts:
            st.markdown("---")
            st.markdown("### ⚠️ Разрешение конфликтов сотрудников")
            st.info("Обнаружены конфликты при объединении сотрудников из XML с сохраненными. Выберите действие для каждого конфликта.")
            
            with st.expander("📋 Список конфликтов", expanded=True):
                for idx, conflict in enumerate(st.session_state.pending_conflicts):
                    existing = conflict['existing']
                    new = conflict['new']
                    conflict_type = conflict['type']
                    # Используем только имя как ключ конфликта
                    conflict_key = new.get('name', '')
                    
                    st.markdown(f"**Конфликт #{idx + 1}** (по имени)")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**В файле:**")
                        st.text(f"Имя: {existing.get('name', 'N/A')}")
                        st.text(f"Max Units: {existing.get('max_units', 'N/A')}")
                    
                    with col2:
                        st.markdown("**Из XML:**")
                        st.text(f"Имя: {new.get('name', 'N/A')}")
                        st.text(f"Max Units: {new.get('max_units', 'N/A')}")
                    
                    # Радио-кнопки выбора действия
                    resolution = st.radio(
                        "Действие:",
                        options=['skip', 'update', 'add_new'],
                        format_func=lambda x: {
                            'skip': 'Пропустить (оставить из файла)',
                            'update': 'Обновить из XML',
                            'add_new': 'Добавить как нового сотрудника'
                        }[x],
                        key=f"conflict_resolution_{idx}",
                        index=0
                    )
                    
                    st.session_state.conflict_resolutions[conflict_key] = resolution
                    st.markdown("---")
                
                if st.button("✅ Применить решения", key="apply_conflict_resolutions", use_container_width=True):
                    # Объединить ресурсы с учетом решений
                    merged_resources = merge_resources(
                        st.session_state.saved_resources,
                        st.session_state.parser.resources,
                        st.session_state.conflict_resolutions
                    )
                    st.session_state.saved_resources = merged_resources
                    
                    # Обновить ресурсы во всех парсерах (сеттер сам обновит все парсеры и кэш)
                    st.session_state.parser.resources = merged_resources
                    
                    # Сохранить в файл
                    save_employees_data(
                        st.session_state.saved_resources,
                        st.session_state.resource_groups
                    )
                    
                    # Очистить конфликты
                    st.session_state.pending_conflicts = []
                    st.session_state.conflict_resolutions = {}
                    
                    # Продолжить инициализацию дат и расчетов
                    today = datetime.now().date()
                    project_start, project_end = st.session_state.parser.get_project_dates()
                    
                    start_candidate = today - timedelta(days=7)
                    days_since_monday = start_candidate.weekday()
                    default_start = start_candidate - timedelta(days=days_since_monday)
                    
                    end_candidate = today + timedelta(days=14)
                    days_until_friday = (4 - end_candidate.weekday()) % 7
                    default_end = end_candidate + timedelta(days=days_until_friday)
                    
                    if project_start and project_end:
                        project_start_date = project_start.date()
                        project_end_date = project_end.date()
                        default_start = max(default_start, project_start_date)
                        default_start = min(default_start, project_end_date)
                        default_end = max(default_end, project_start_date)
                        default_end = min(default_end, project_end_date)
                    
                    st.session_state.date_range_start = default_start
                    st.session_state.date_range_end = default_end
                    st.session_state.workload_data = st.session_state.parser.get_resource_workload_data(
                        st.session_state.date_range_start,
                        st.session_state.date_range_end
                    )
                    st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                    st.success("✓ Конфликты разрешены, файл успешно проанализирован!")
                    st.rerun()
        
        # Фильтр временного диапазона
        if st.session_state.parser is not None:
            st.markdown("---")
            st.markdown("### 📅 Временной диапазон анализа")
            
            # Получить даты проекта
            project_start, project_end = st.session_state.parser.get_project_dates()
            
            if project_start and project_end:
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input(
                        "Начало",
                        value=st.session_state.date_range_start or project_start.date(),
                        min_value=project_start.date(),
                        max_value=project_end.date(),
                        help="Начальная дата анализа"
                    )
                with col2:
                    end_date = st.date_input(
                        "Конец",
                        value=st.session_state.date_range_end or project_end.date(),
                        min_value=project_start.date(),
                        max_value=project_end.date(),
                        help="Конечная дата анализа"
                    )
                
                # Обновить session state если изменились
                if start_date != st.session_state.date_range_start or end_date != st.session_state.date_range_end:
                    st.session_state.date_range_start = start_date
                    st.session_state.date_range_end = end_date
                    # Пересчитать данные с учетом нового диапазона
                    if st.session_state.parser:
                        st.session_state.workload_data = st.session_state.parser.get_resource_workload_data(
                            st.session_state.date_range_start,
                            st.session_state.date_range_end
                        )
                        st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                        # Сбросить timeline_data и optimization_results для пересчета
                        st.session_state.timeline_data = None
                        st.session_state.optimization_results = None
                    st.rerun()
        
        st.markdown("---")
        st.markdown("### ℹ️ О программе")
        st.markdown("""
        Этот инструмент помогает:
        - Выявить перегруженные ресурсы (>100%)
        - Найти недоиспользованные мощности (<70%)
        - **Оптимизировать распределение смещением задач**
        - **Анализировать временную загрузку по неделям**
        - **Интерактивно заменять специалистов**
        - Получить рекомендации по балансировке нагрузки
        - Экспортировать отчёты анализа
        """)
    
    # Основной контент
    if st.session_state.workload_data is None:
        # Экран приветствия
        st.info("👆 Загрузите XML-файл Microsoft Project для начала анализа")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #FF4B4B;'>Выявление перегрузки</h3>
                    <p>Определение ресурсов с нагрузкой более 100%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #107C10;'>Оптимизация распределения</h3>
                    <p>Рекомендации по улучшению распределения ресурсов</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #0078D4;'>Экспорт отчётов</h3>
                    <p>Скачайте анализ в формате CSV или PDF</p>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Пример анализа")
        st.markdown("Загрузите файл, чтобы увидеть подробный анализ ресурсов с:")
        st.markdown("- Цветными индикаторами рабочей нагрузки")
        st.markdown("- Назначениями задач по ресурсам")
        st.markdown("- Практическими рекомендациями")
        st.markdown("- Сводной статистикой")
        
    else:
        # Отображение анализа
        workload_data = st.session_state.workload_data
        analysis = st.session_state.analysis
        
        # Сводные метрики
        st.markdown("### 📊 Панель управления")
        
        # Получение информации о длительности проекта
        project_weeks = workload_data[0]['project_weeks'] if workload_data else 4
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Всего ресурсов", len(workload_data))
        
        with col2:
            st.metric("Длительность проекта", f"{project_weeks:.1f} нед.")
        
        with col3:
            st.metric("Перегружено", len(analysis['overloaded']), 
                     delta=f"{len(analysis['overloaded'])}" if len(analysis['overloaded']) > 0 else None,
                     delta_color="inverse")
        
        with col4:
            st.metric("Оптимально", len(analysis['optimal']),
                     delta_color="off")
        
        with col5:
            st.metric("Недоиспользуется", len(analysis['underutilized']),
                     delta=f"{len(analysis['underutilized'])}" if len(analysis['underutilized']) > 0 else None,
                     delta_color="normal")
        
        # Информация о периоде анализа
        if st.session_state.date_range_start and st.session_state.date_range_end:
            business_days = calculate_business_days(st.session_state.date_range_start, st.session_state.date_range_end)
            work_capacity = calculate_work_capacity(business_days)
            
            # Проверка корректности значений перед отображением
            if business_days is not None and business_days >= 0 and work_capacity is not None and work_capacity >= 0:
                # Material Design 3 панель управления периодом
                period_str = f"{st.session_state.date_range_start.strftime('%d.%m.%Y')} - {st.session_state.date_range_end.strftime('%d.%m.%Y')}"
                st.markdown(md3_info_panel(period_str, business_days, work_capacity), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Объединенная секция управления персоналом
        with st.expander("### 👥 Управление персоналом", expanded=True):
            # Инициализация applied_group если нужно
            if not hasattr(st.session_state, 'applied_group'):
                st.session_state.applied_group = None
            # Инициализация selected_resources_state для синхронизации выбора ресурсов
            if 'selected_resources_state' not in st.session_state:
                st.session_state.selected_resources_state = None
            # Инициализация счетчика для динамического ключа multiselect
            if 'multiselect_key_counter' not in st.session_state:
                st.session_state.multiselect_key_counter = 0
            
            # Инициализация переменных для использования вне табов
            selected_resources = []
            display_data = workload_data
            
            # Три таба: Текущий выбор, Управление группами и Управление сотрудниками
            tab1, tab2, tab3 = st.tabs(["🔍 Текущий выбор", "⚙️ Управление группами", "👤 Управление сотрудниками"])
            
            # ========== ТАБ 1: ТЕКУЩИЙ ВЫБОР ==========
            with tab1:
                # Выбор из сохраненных групп
                if st.session_state.resource_groups:
                    st.markdown("**Выбрать из сохраненных групп:**")
                    sorted_group_names = sorted(st.session_state.resource_groups.keys(), key=str.lower)
                    group_names = ["-- Не выбрано --"] + sorted_group_names
                    selected_group_tab1 = st.selectbox(
                        "Выберите группу:",
                        options=group_names,
                        key="selected_group_tab1_dropdown"
                    )
                    
                    # Кнопка для применения группы
                    if selected_group_tab1 != "-- Не выбрано --":
                        group_resources_tab1 = st.session_state.resource_groups[selected_group_tab1]
                        st.caption(f"👥 {len(group_resources_tab1)} человек: {', '.join(group_resources_tab1[:3])}{'...' if len(group_resources_tab1) > 3 else ''}")
                        
                        if st.button("✅ Применить группу", key="apply_group_tab1_btn"):
                            st.session_state.applied_group = (selected_group_tab1, group_resources_tab1)
                            # Обновить selected_resources_state списком ресурсов из группы
                            st.session_state.selected_resources_state = group_resources_tab1.copy()
                            # Увеличить счетчик для принудительного пересоздания multiselect
                            st.session_state.multiselect_key_counter += 1
                            st.success(f"✓ Группа '{selected_group_tab1}' применена ({len(group_resources_tab1)} чел.)")
                            st.rerun()
                    
                    st.markdown("---")
                
                all_names = sorted([item['resource_name'] for item in workload_data], key=str.lower)
                
                # Поиск по имени
                col1, col2 = st.columns([3, 1])
                with col1:
                    search_term = st.text_input("Поиск по фамилии или имени:", placeholder="например, Иванов")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    show_all = st.checkbox("Показать всех", value=True)
                
                # Фильтрация данных по поиску
                if show_all or not search_term:
                    filtered_data = workload_data
                else:
                    filtered_data = [item for item in workload_data 
                                   if search_term.lower() in item['resource_name'].lower()]
                
                # Сортировка filtered_data по алфавиту
                filtered_data = sorted(filtered_data, key=lambda x: x['resource_name'].lower())
                
                # Получить список всех ресурсов из XML (не отфильтрованных поиском)
                # Использовать workload_data, чтобы всегда иметь все ресурсы из XML
                xml_resource_names = [item['resource_name'] for item in workload_data] if workload_data else []
                
                # Определить состав группы, если она применена
                group_resources_for_select = []
                if st.session_state.applied_group:
                    group_name, group_resources = st.session_state.applied_group
                    group_resources_for_select = group_resources.copy()
                
                # Объединить ресурсы из XML и группы для options в multiselect
                # Сначала ресурсы из группы (чтобы они были видны), затем из XML
                all_options = []
                # Добавить ресурсы из группы
                for name in group_resources_for_select:
                    if name not in all_options:
                        all_options.append(name)
                # Добавить ресурсы из XML, которых еще нет
                for name in xml_resource_names:
                    if name not in all_options:
                        all_options.append(name)
                # Сортировать по алфавиту
                all_options = sorted(all_options, key=str.lower)
                
                if not filtered_data and not group_resources_for_select:
                    st.warning("Ресурсы, соответствующие вашему запросу, не найдены.")
                    selected_resources = []
                    display_data = []
                else:
                    # Определить default значения для multiselect
                    if st.session_state.applied_group:
                        # Группа применена: использовать selected_resources_state или ресурсы из группы
                        group_name, group_resources = st.session_state.applied_group
                        st.info(f"📌 Применена группа '{group_name}' ({len(group_resources)} чел.). Вы можете добавить дополнительные ресурсы из списка ниже.")
                        # Использовать selected_resources_state, если он установлен, иначе использовать ресурсы из группы
                        if st.session_state.selected_resources_state is not None:
                            default_resources = st.session_state.selected_resources_state.copy()
                        else:
                            default_resources = group_resources.copy()
                    else:
                        # Группа не применена: использовать selected_resources_state или всех из filtered_data
                        if st.session_state.selected_resources_state is not None:
                            default_resources = st.session_state.selected_resources_state.copy()
                        else:
                            default_resources = xml_resource_names.copy()
                    
                    # Определить ресурсы, которых нет в XML (для подсветки)
                    resources_not_in_xml = [name for name in all_options if name not in xml_resource_names]
                    
                    # Добавить CSS и JavaScript для подсветки ресурсов, которых нет в XML
                    if resources_not_in_xml:
                        # Создать JSON-строку для JavaScript
                        resources_not_in_xml_json = json.dumps(resources_not_in_xml, ensure_ascii=False)
                        
                        highlight_css_js = f"""
                        <style>
                            /* Подсветка опций multiselect, которых нет в XML */
                            div[data-baseweb="select"] ul[role="listbox"] li {{
                                transition: background-color 0.2s;
                            }}
                            
                            /* Желтая подсветка для ресурсов, которых нет в XML */
                            div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"] {{
                                background-color: #FFF9C4 !important;
                                border-left: 3px solid #FBC02D !important;
                            }}
                            
                            div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"]:hover {{
                                background-color: #FFF59D !important;
                            }}
                            
                            /* Подсветка выбранных опций, которых нет в XML */
                            div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"][aria-selected="true"] {{
                                background-color: #FFF176 !important;
                            }}
                            
                            /* Желтая подсветка для выбранных элементов (chips), которых нет в XML */
                            div[data-baseweb="select"] span[data-resource-not-in-xml="true"],
                            div[data-baseweb="select"] div[data-resource-not-in-xml="true"],
                            div[data-baseweb="select"] [data-resource-not-in-xml="true"] {{
                                background-color: #FFF9C4 !important;
                                color: #856404 !important;
                                border: 1px solid #FBC02D !important;
                                border-radius: 4px !important;
                                padding: 2px 6px !important;
                                margin: 2px !important;
                            }}
                            
                            /* Стили для выбранных значений в multiselect через data-baseweb */
                            div[data-baseweb="select"] [data-baseweb="tag"][data-resource-not-in-xml="true"],
                            div[data-baseweb="select"] [data-baseweb="multiValue"][data-resource-not-in-xml="true"] {{
                                background-color: #FFF9C4 !important;
                                color: #856404 !important;
                                border: 1px solid #FBC02D !important;
                            }}
                            
                            /* Универсальный селектор для всех элементов с атрибутом */
                            [data-resource-not-in-xml="true"] {{
                                background-color: #FFF9C4 !important;
                                color: #856404 !important;
                                border: 1px solid #FBC02D !important;
                            }}
                        </style>
                        <script>
                            (function() {{
                                const resourcesNotInXml = {resources_not_in_xml_json};
                                
                                function highlightResources() {{
                                    // Найти все multiselect контейнеры
                                    const selectContainers = document.querySelectorAll('div[data-baseweb="select"]');
                                    
                                    selectContainers.forEach(selectContainer => {{
                                        // Проверить, что это нужный multiselect (по label или key)
                                        const label = selectContainer.closest('.stMultiSelect') || 
                                                     selectContainer.closest('[data-testid*="stMultiSelect"]');
                                        
                                        if (!label) return;
                                        
                                        // Найти список опций
                                        const listbox = selectContainer.querySelector('ul[role="listbox"]');
                                        if (listbox) {{
                                            // Пройти по всем опциям
                                            const options = listbox.querySelectorAll('li[role="option"]');
                                            options.forEach(option => {{
                                                const optionText = option.textContent.trim();
                                                // Проверить, есть ли этот ресурс в списке тех, кого нет в XML
                                                if (resourcesNotInXml.some(resource => optionText === resource)) {{
                                                    option.setAttribute('data-resource-not-in-xml', 'true');
                                                }} else {{
                                                    option.removeAttribute('data-resource-not-in-xml');
                                                }}
                                            }});
                                        }}
                                        
                                        // Найти выбранные элементы (chips/tags)
                                        // В Streamlit multiselect выбранные значения находятся в разных местах
                                        // Попробуем найти их через различные селекторы
                                        
                                        // Метод 1: Найти через data-baseweb="tag" или data-baseweb="multiValue"
                                        const tags1 = selectContainer.querySelectorAll('[data-baseweb="tag"], [data-baseweb="multiValue"]');
                                        tags1.forEach(tag => {{
                                            const text = tag.textContent.trim();
                                            if (text && resourcesNotInXml.some(resource => text === resource)) {{
                                                tag.setAttribute('data-resource-not-in-xml', 'true');
                                                tag.style.setProperty('background-color', '#FFF9C4', 'important');
                                                tag.style.setProperty('color', '#856404', 'important');
                                                tag.style.setProperty('border', '1px solid #FBC02D', 'important');
                                            }}
                                        }});
                                        
                                        // Метод 2: Найти все span и div, которые не в dropdown
                                        const allElements = selectContainer.querySelectorAll('span, div');
                                        allElements.forEach(element => {{
                                            // Пропустить элементы внутри dropdown
                                            if (element.closest('ul[role="listbox"]')) {{
                                                return;
                                            }}
                                            
                                            // Пропустить элементы, которые уже обработаны
                                            if (element.closest('[data-baseweb="tag"]') || element.closest('[data-baseweb="multiValue"]')) {{
                                                return;
                                            }}
                                            
                                            const text = element.textContent.trim();
                                            // Проверить точное совпадение с ресурсами, которых нет в XML
                                            let matchingResource = null;
                                            for (let i = 0; i < resourcesNotInXml.length; i++) {{
                                                const resource = resourcesNotInXml[i];
                                                // Точное совпадение или совпадение с учетом пробелов
                                                if (text === resource || text.replace(/\\s+/g, ' ') === resource.replace(/\\s+/g, ' ')) {{
                                                    matchingResource = resource;
                                                    break;
                                                }}
                                            }}
                                            
                                            if (matchingResource) {{
                                                // Проверить, что это не пустой элемент и не часть структуры
                                                if (text.length > 0 && text.length < 200 && !element.querySelector('svg') && !element.querySelector('input')) {{
                                                    // Проверить, что это не родительский элемент с множеством дочерних
                                                    if (element.children.length < 3) {{
                                                        element.setAttribute('data-resource-not-in-xml', 'true');
                                                        // Применить стили с !important через setProperty
                                                        element.style.setProperty('background-color', '#FFF9C4', 'important');
                                                        element.style.setProperty('color', '#856404', 'important');
                                                        element.style.setProperty('border', '1px solid #FBC02D', 'important');
                                                        element.style.setProperty('border-radius', '4px', 'important');
                                                        element.style.setProperty('padding', '2px 6px', 'important');
                                                        element.style.setProperty('margin', '2px', 'important');
                                                        element.style.setProperty('display', 'inline-block', 'important');
                                                    }}
                                                }}
                                            }} else if (element.hasAttribute('data-resource-not-in-xml')) {{
                                                // Убрать стили, если элемент больше не соответствует
                                                element.removeAttribute('data-resource-not-in-xml');
                                                element.style.removeProperty('background-color');
                                                element.style.removeProperty('color');
                                                element.style.removeProperty('border');
                                                element.style.removeProperty('border-radius');
                                                element.style.removeProperty('padding');
                                                element.style.removeProperty('margin');
                                                element.style.removeProperty('display');
                                            }}
                                        }});
                                    }});
                                }}
                                
                                // Выполнить при загрузке
                                if (document.readyState === 'loading') {{
                                    document.addEventListener('DOMContentLoaded', highlightResources);
                                }} else {{
                                    highlightResources();
                                }}
                                
                                // Выполнить при изменении (для динамического обновления)
                                const observer = new MutationObserver(function(mutations) {{
                                    let shouldHighlight = false;
                                    mutations.forEach(function(mutation) {{
                                        if (mutation.addedNodes.length > 0 || mutation.type === 'childList') {{
                                            shouldHighlight = true;
                                        }}
                                    }});
                                    if (shouldHighlight) {{
                                        setTimeout(highlightResources, 50);
                                    }}
                                }});
                                
                                observer.observe(document.body, {{
                                    childList: true,
                                    subtree: true
                                }});
                                
                                // Также выполнить после небольшой задержки для Streamlit
                                setTimeout(highlightResources, 100);
                                setTimeout(highlightResources, 300);
                                setTimeout(highlightResources, 500);
                                setTimeout(highlightResources, 1000);
                                setTimeout(highlightResources, 2000);
                                
                                // Выполнить при клике (для обновления при открытии dropdown)
                                document.addEventListener('click', function() {{
                                    setTimeout(highlightResources, 100);
                                }});
                                
                                // Выполнить при изменении значения (для обновления выбранных элементов)
                                function setupInputObserver() {{
                                    const selectContainers = document.querySelectorAll('div[data-baseweb="select"]');
                                    selectContainers.forEach(container => {{
                                        const inputObserver = new MutationObserver(function(mutations) {{
                                            let shouldUpdate = false;
                                            mutations.forEach(function(mutation) {{
                                                if (mutation.type === 'childList' || mutation.type === 'attributes') {{
                                                    shouldUpdate = true;
                                                }}
                                            }});
                                            if (shouldUpdate) {{
                                                setTimeout(highlightResources, 50);
                                            }}
                                        }});
                                        
                                        inputObserver.observe(container, {{
                                            childList: true,
                                            subtree: true,
                                            attributes: true,
                                            attributeFilter: ['class', 'style']
                                        }});
                                    }});
                                }}
                                
                                // Настроить observer после небольшой задержки
                                setTimeout(setupInputObserver, 200);
                                setTimeout(setupInputObserver, 1000);
                            }})();
                        </script>
                        """
                        st.markdown(highlight_css_js, unsafe_allow_html=True)
                    
                    # Множественный выбор - options содержат ресурсы из группы + ресурсы из XML
                    # Использовать динамический ключ для принудительного пересоздания виджета при применении группы
                    multiselect_key = f"current_selection_multiselect_{st.session_state.multiselect_key_counter}"
                    selected_resources = st.multiselect(
                        "Выберите конкретные ресурсы для анализа:",
                        options=all_options,
                        default=default_resources,
                        key=multiselect_key
                    )
                    
                    # Синхронизировать изменения в multiselect с selected_resources_state
                    current_state = st.session_state.selected_resources_state
                    if current_state is None or selected_resources != current_state:
                        st.session_state.selected_resources_state = selected_resources.copy()
                    
                    # НОВАЯ ФУНКЦИЯ: Быстрое сохранение текущего выбора как группы
                    if selected_resources and len(selected_resources) > 0:
                        st.markdown("---")
                        with st.expander("💾 Сохранить текущий выбор как группу"):
                            # Инициализация состояния диалога
                            if 'group_save_dialog' not in st.session_state:
                                st.session_state.group_save_dialog = None
                            if 'group_save_new_name' not in st.session_state:
                                st.session_state.group_save_new_name = ""
                            
                            quick_group_name = st.text_input(
                                "Название новой группы:",
                                placeholder="например, Команда А",
                                key="quick_save_group_name"
                            )
                            
                            # Если диалог активен для этой группы, показать диалог выбора
                            if st.session_state.group_save_dialog == quick_group_name and quick_group_name:
                                st.warning(f"Группа '{quick_group_name}' уже существует. Выберите действие:")
                                
                                save_action = st.radio(
                                    "Что вы хотите сделать?",
                                    ["Перезаписать группу", "Создать новую группу", "Отменить"],
                                    key="group_save_action_radio"
                                )
                                
                                # Если выбрано "Создать новую группу", показать поле для нового имени
                                if save_action == "Создать новую группу":
                                    st.session_state.group_save_new_name = st.text_input(
                                        "Введите название новой группы:",
                                        value=st.session_state.group_save_new_name,
                                        placeholder="например, Команда А (копия)",
                                        key="group_save_new_name_input"
                                    )
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ Подтвердить", key="confirm_save_btn"):
                                        if save_action == "Перезаписать группу":
                                            # Перезаписать группу с новым составом
                                            st.session_state.resource_groups[quick_group_name] = selected_resources.copy()
                                            # Обновить примененную группу, если она была изменена
                                            if st.session_state.applied_group and st.session_state.applied_group[0] == quick_group_name:
                                                st.session_state.applied_group = (quick_group_name, selected_resources.copy())
                                                # Обновить selected_resources_state списком ресурсов из перезаписанной группы
                                                st.session_state.selected_resources_state = selected_resources.copy()
                                            # Сохранить в файл
                                            save_employees_data(
                                                st.session_state.saved_resources,
                                                st.session_state.resource_groups
                                            )
                                            st.success(f"✓ Группа '{quick_group_name}' перезаписана ({len(selected_resources)} чел.)")
                                            st.session_state.group_save_dialog = None
                                            st.session_state.group_save_new_name = ""
                                            st.rerun()
                                        elif save_action == "Создать новую группу":
                                            # Создать новую группу с новым именем
                                            new_name = st.session_state.group_save_new_name
                                            if not new_name:
                                                st.error("Введите название новой группы")
                                            elif new_name in st.session_state.resource_groups:
                                                st.error("Группа с таким названием уже существует")
                                            else:
                                                st.session_state.resource_groups[new_name] = selected_resources.copy()
                                                # Сохранить в файл
                                                save_employees_data(
                                                    st.session_state.saved_resources,
                                                    st.session_state.resource_groups
                                                )
                                                st.success(f"✓ Группа '{new_name}' создана ({len(selected_resources)} чел.)")
                                                st.session_state.group_save_dialog = None
                                                st.session_state.group_save_new_name = ""
                                                st.rerun()
                                        else:  # Отменить
                                            st.session_state.group_save_dialog = None
                                            st.session_state.group_save_new_name = ""
                                            st.rerun()
                                with col2:
                                    if st.button("❌ Отменить", key="cancel_save_btn"):
                                        st.session_state.group_save_dialog = None
                                        st.session_state.group_save_new_name = ""
                                        st.rerun()
                            else:
                                # Кнопка сохранения (показывается только когда диалог не активен)
                                if st.button("💾 Сохранить", key="quick_save_btn"):
                                    if not quick_group_name:
                                        st.error("Введите название группы")
                                    elif quick_group_name in st.session_state.resource_groups:
                                        # Активировать диалог выбора
                                        st.session_state.group_save_dialog = quick_group_name
                                        st.rerun()
                                    else:
                                        # Группа не существует, создать новую
                                        st.session_state.resource_groups[quick_group_name] = selected_resources.copy()
                                        # Сохранить в файл
                                        save_employees_data(
                                            st.session_state.saved_resources,
                                            st.session_state.resource_groups
                                        )
                                        st.success(f"✓ Группа '{quick_group_name}' создана ({len(selected_resources)} чел.)")
                                        st.rerun()
                    
                    if selected_resources:
                        # Использовать workload_data вместо filtered_data для отображения всех выбранных ресурсов
                        # Это позволяет показывать ресурсы из группы, даже если они не проходят фильтр поиска
                        display_data = [item for item in workload_data 
                                      if item['resource_name'] in selected_resources]
                    else:
                        display_data = workload_data
            
            # ========== ТАБ 2: УПРАВЛЕНИЕ ГРУППАМИ ==========
            with tab2:
                # Выбор и применение сохраненной группы
                if st.session_state.resource_groups:
                    st.markdown("**Применить сохраненную группу:**")
                    sorted_group_names = sorted(st.session_state.resource_groups.keys(), key=str.lower)
                    group_names = ["-- Не выбрано --"] + sorted_group_names
                    selected_group = st.selectbox(
                        "Выберите группу:",
                        options=group_names,
                        key="selected_group_dropdown"
                    )
                    
                    # Кнопка для применения группы
                    if selected_group != "-- Не выбрано --":
                        group_resources = st.session_state.resource_groups[selected_group]
                        st.caption(f"👥 {len(group_resources)} человек: {', '.join(group_resources[:3])}{'...' if len(group_resources) > 3 else ''}")
                        
                        if st.button("✅ Применить группу", key="apply_group_btn"):
                            st.session_state.applied_group = (selected_group, group_resources)
                            # Обновить selected_resources_state списком ресурсов из группы
                            st.session_state.selected_resources_state = group_resources.copy()
                            # Увеличить счетчик для принудительного пересоздания multiselect
                            st.session_state.multiselect_key_counter += 1
                            st.success(f"✓ Группа '{selected_group}' применена ({len(group_resources)} чел.)")
                            st.rerun()
                    
                    st.markdown("---")
                else:
                    st.info("У вас пока нет сохраненных групп. Создайте новую ниже.")
                
                # Создание новой группы с нуля
                st.markdown("**Создать новую группу:**")
                with st.expander("➕ Создать группу", expanded=not st.session_state.resource_groups):
                    new_group_name = st.text_input("Название группы:", placeholder="например, Разработчики", key="new_group_name_input")
                    
                    # Использовать полный список сохраненных сотрудников
                    all_names = sorted([r.get('name', '') for r in st.session_state.saved_resources], key=str.lower)
                    new_group_resources = st.multiselect(
                        "Выберите участников группы:",
                        options=all_names,
                        key="new_group_resources"
                    )
                    
                    if st.button("💾 Сохранить группу", key="save_new_group_btn"):
                        if not new_group_name:
                            st.error("Введите название группы")
                        elif not new_group_resources:
                            st.error("Выберите хотя бы одного участника")
                        elif new_group_name in st.session_state.resource_groups:
                            st.error("Группа с таким названием уже существует")
                        else:
                            st.session_state.resource_groups[new_group_name] = new_group_resources
                            # Сохранить в файл
                            save_employees_data(
                                st.session_state.saved_resources,
                                st.session_state.resource_groups
                            )
                            st.success(f"✓ Группа '{new_group_name}' создана ({len(new_group_resources)} чел.)")
                            st.rerun()
                
                # Управление существующими группами
                if st.session_state.resource_groups:
                    st.markdown("---")
                    st.markdown("**Управление группами:**")
                    for group_name in list(st.session_state.resource_groups.keys()):
                        group_members = st.session_state.resource_groups[group_name]
                        
                        # Заголовок группы с кнопкой удаления
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(f"**{group_name}** ({len(group_members)} чел.)")
                        with col2:
                            if st.button("🗑️", key=f"delete_{group_name}", help=f"Удалить группу '{group_name}'"):
                                del st.session_state.resource_groups[group_name]
                                if st.session_state.applied_group and st.session_state.applied_group[0] == group_name:
                                    st.session_state.applied_group = None
                                    # Сбросить selected_resources_state при удалении примененной группы
                                    st.session_state.selected_resources_state = None
                                # Сохранить в файл
                                save_employees_data(
                                    st.session_state.saved_resources,
                                    st.session_state.resource_groups
                                )
                                st.success(f"✓ Группа '{group_name}' удалена")
                                st.rerun()
                        
                        # Expander для редактирования состава группы
                        with st.expander(f"✏️ Редактировать группу '{group_name}'"):
                            # Использовать полный список сохраненных сотрудников
                            all_names = sorted([r.get('name', '') for r in st.session_state.saved_resources], key=str.lower)
                            edited_group_resources = st.multiselect(
                                "Выберите участников группы:",
                                options=all_names,
                                default=group_members,
                                key=f"edit_group_{group_name}"
                            )
                            
                            if st.button("💾 Сохранить изменения", key=f"save_edit_{group_name}"):
                                st.session_state.resource_groups[group_name] = edited_group_resources.copy()
                                # Обновить примененную группу, если она была изменена
                                if st.session_state.applied_group and st.session_state.applied_group[0] == group_name:
                                    st.session_state.applied_group = (group_name, edited_group_resources.copy())
                                    # Обновить selected_resources_state списком ресурсов из обновленной группы
                                    st.session_state.selected_resources_state = edited_group_resources.copy()
                                # Сохранить в файл
                                save_employees_data(
                                    st.session_state.saved_resources,
                                    st.session_state.resource_groups
                                )
                                st.success(f"✓ Группа '{group_name}' обновлена ({len(edited_group_resources)} чел.)")
                                st.rerun()
                        
                        st.markdown("")  # Добавить отступ между группами
            
            # ========== ТАБ 3: УПРАВЛЕНИЕ СОТРУДНИКАМИ ==========
            with tab3:
                st.markdown("**Управление перечнем сотрудников:**")
                
                # Отображение списка сотрудников
                if st.session_state.saved_resources:
                    st.markdown(f"**Всего сотрудников: {len(st.session_state.saved_resources)}**")
                    
                    # Инициализация состояния для редактирования
                    if 'editing_employee' not in st.session_state:
                        st.session_state.editing_employee = None
                    
                    # Обработка удаления
                    if 'delete_employee_name' in st.session_state and st.session_state.delete_employee_name:
                        employee_name_to_delete = st.session_state.delete_employee_name
                        st.session_state.saved_resources = [
                            r for r in st.session_state.saved_resources 
                            if r.get('name') != employee_name_to_delete
                        ]
                        # Обновить группы - удалить сотрудника из всех групп
                        for group_name in st.session_state.resource_groups:
                            st.session_state.resource_groups[group_name] = [
                                name for name in st.session_state.resource_groups[group_name]
                                if name != employee_name_to_delete
                            ]
                        # Сохранить в файл
                        save_employees_data(
                            st.session_state.saved_resources,
                            st.session_state.resource_groups
                        )
                        st.success(f"✓ Сотрудник '{employee_name_to_delete}' удален")
                        st.session_state.delete_employee_name = None
                        st.session_state.editing_employee = None
                        st.rerun()
                    
                    # Инициализация состояния для фильтров и сортировки
                    if 'filter_name' not in st.session_state:
                        st.session_state.filter_name = ''
                    if 'filter_max_units' not in st.session_state:
                        st.session_state.filter_max_units = ''
                    if 'sort_column' not in st.session_state:
                        st.session_state.sort_column = 'Имя'
                    if 'sort_direction' not in st.session_state:
                        st.session_state.sort_direction = 'По возрастанию'
                    
                    # Секция фильтров и сортировки
                    st.markdown("---")
                    st.markdown("**Фильтры и сортировка:**")
                    
                    # Фильтры
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        filter_name = st.text_input("Фильтр по имени:", value=st.session_state.filter_name, key="filter_name_input", placeholder="Введите имя...")
                        st.session_state.filter_name = filter_name
                    with filter_col2:
                        filter_max_units = st.text_input("Фильтр по Max Units:", value=st.session_state.filter_max_units, key="filter_max_units_input", placeholder="Введите значение...")
                        st.session_state.filter_max_units = filter_max_units
                    
                    # Сортировка
                    sort_col1, sort_col2 = st.columns(2)
                    with sort_col1:
                        sort_column = st.selectbox(
                            "Сортировать по:",
                            options=['Имя', 'Max Units'],
                            index=['Имя', 'Max Units'].index(st.session_state.sort_column) if st.session_state.sort_column in ['Имя', 'Max Units'] else 0,
                            key="sort_column_select"
                        )
                        st.session_state.sort_column = sort_column
                    with sort_col2:
                        sort_direction = st.radio(
                            "Направление сортировки:",
                            options=['По возрастанию', 'По убыванию'],
                            index=0 if st.session_state.sort_direction == 'По возрастанию' else 1,
                            key="sort_direction_radio",
                            horizontal=True
                        )
                        st.session_state.sort_direction = sort_direction
                    
                    # Применение фильтров
                    filtered_resources = st.session_state.saved_resources.copy()
                    
                    if st.session_state.filter_name:
                        filtered_resources = [
                            r for r in filtered_resources 
                            if st.session_state.filter_name.lower() in str(r.get('name', '')).lower()
                        ]
                    
                    if st.session_state.filter_max_units:
                        filtered_resources = [
                            r for r in filtered_resources 
                            if st.session_state.filter_max_units.lower() in str(r.get('max_units', '')).lower()
                        ]
                    
                    # Применение сортировки
                    sort_reverse = st.session_state.sort_direction == 'По убыванию'
                    
                    if st.session_state.sort_column == 'Имя':
                        sorted_resources = sorted(
                            filtered_resources,
                            key=lambda x: str(x.get('name', '')).lower(),
                            reverse=sort_reverse
                        )
                    elif st.session_state.sort_column == 'Max Units':
                        sorted_resources = sorted(
                            filtered_resources,
                            key=lambda x: float(str(x.get('max_units', '0')).replace(',', '.')) if str(x.get('max_units', '0')).replace(',', '.').replace('.', '').isdigit() else 0,
                            reverse=sort_reverse
                        )
                    else:
                        sorted_resources = filtered_resources
                    
                    # Показать количество отфильтрованных записей
                    if len(filtered_resources) != len(st.session_state.saved_resources):
                        st.info(f"Показано {len(filtered_resources)} из {len(st.session_state.saved_resources)} сотрудников")
                    
                    # CSS стили для таблицы сотрудников
                    st.markdown("""
                    <style>
                    /* Уменьшение высоты кнопок до высоты текста в таблице сотрудников */
                    button[kind="secondary"] {
                        height: auto !important;
                        min-height: 1.5em !important;
                        padding: 0.25em 0.5em !important;
                        line-height: 1.2 !important;
                    }
                    
                    /* Уменьшение межстрочного интервала в таблице */
                    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
                        margin-bottom: 2px !important;
                        padding-bottom: 2px !important;
                    }
                    
                    /* Уменьшение отступов в контейнерах строк таблицы */
                    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div {
                        margin-bottom: 2px !important;
                    }
                    
                    /* Уменьшение отступов между колонками в строках */
                    div[data-testid="column"] {
                        margin-bottom: 2px !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # JavaScript для применения стилей прокрутки к таблице
                    st.markdown("""
                    <script>
                    setTimeout(function() {
                        // Найти контейнер с заголовками таблицы
                        const headers = Array.from(document.querySelectorAll('*')).find(el => 
                            el.textContent && el.textContent.includes('Имя') && 
                            el.textContent.includes('Max Units')
                        );
                        if (headers) {
                            // Найти родительский контейнер Streamlit
                            let container = headers.closest('[data-testid="stVerticalBlock"]');
                            if (!container) {
                                container = headers.closest('div[class*="block-container"]');
                            }
                            if (container) {
                                container.style.maxHeight = '400px';
                                container.style.overflowY = 'auto';
                                container.style.overflowX = 'auto';
                                container.style.border = '1px solid #e0e0e0';
                                container.style.borderRadius = '4px';
                                container.style.padding = '10px';
                            }
                            
                            // Применить стили к кнопкам в таблице
                            const buttons = container.querySelectorAll('button[kind="secondary"]');
                            buttons.forEach(button => {
                                button.style.height = 'auto';
                                button.style.minHeight = '1.5em';
                                button.style.padding = '0.25em 0.5em';
                                button.style.lineHeight = '1.2';
                            });
                            
                            // Уменьшить межстрочный интервал между строками таблицы
                            const verticalBlocks = container.querySelectorAll('[data-testid="stVerticalBlock"]');
                            verticalBlocks.forEach((block, index) => {
                                // Пропустить первый блок (заголовки) и применить к остальным
                                if (index > 0) {
                                    block.style.marginBottom = '2px';
                                    block.style.paddingBottom = '2px';
                                    
                                    // Также уменьшить отступы внутри блока
                                    const innerDivs = block.querySelectorAll('div[data-testid="stVerticalBlock"]');
                                    innerDivs.forEach(innerDiv => {
                                        innerDiv.style.marginBottom = '2px';
                                        innerDiv.style.paddingBottom = '2px';
                                    });
                                    
                                    // Уменьшить отступы в колонках
                                    const columns = block.querySelectorAll('[data-testid="column"]');
                                    columns.forEach(column => {
                                        column.style.marginBottom = '2px';
                                    });
                                }
                            });
                        }
                    }, 200);
                    </script>
                    """, unsafe_allow_html=True)
                    
                    # Заголовки таблицы
                    st.markdown("---")
                    header_col1, header_col2, header_col3, header_col4 = st.columns([3, 2, 1, 1])
                    with header_col1:
                        st.markdown("**Имя**")
                    with header_col2:
                        st.markdown("**Max Units**")
                    with header_col3:
                        st.markdown("**Действия**")
                    with header_col4:
                        st.markdown("")
                    
                    # Отображение списка сотрудников с кнопками
                    for idx, employee in enumerate(sorted_resources):
                        employee_name = employee.get('name', '')
                        employee_max_units = employee.get('max_units', '1.0')
                        
                        # Если этот сотрудник редактируется
                        if st.session_state.editing_employee == employee_name:
                            with st.container():
                                st.markdown("---")
                                st.markdown(f"**✏️ Редактирование: {employee_name}**")
                                
                                col1, col2, col3 = st.columns([2, 2, 1])
                                with col1:
                                    edited_name = st.text_input("Имя:", value=employee_name, key=f"edit_name_{idx}")
                                with col2:
                                    edited_max_units = st.text_input("Max Units:", value=employee_max_units, key=f"edit_max_units_{idx}")
                                with col3:
                                    st.markdown("<br>", unsafe_allow_html=True)  # Отступ для выравнивания
                                    save_col, cancel_col = st.columns(2)
                                    with save_col:
                                        if st.button("💾", key=f"save_{idx}", help="Сохранить"):
                                            # Проверить на дубликаты (кроме текущего)
                                            existing_names = [r.get('name') for r in st.session_state.saved_resources if r.get('name') != employee_name]
                                            
                                            if edited_name in existing_names:
                                                st.error(f"Сотрудник с именем '{edited_name}' уже существует")
                                            else:
                                                # Обновить данные сотрудника
                                                old_name = employee['name']
                                                employee['name'] = edited_name
                                                employee['max_units'] = edited_max_units
                                                
                                                # Обновить имя в группах, если оно изменилось
                                                if edited_name != old_name:
                                                    for group_name in st.session_state.resource_groups:
                                                        if old_name in st.session_state.resource_groups[group_name]:
                                                            index = st.session_state.resource_groups[group_name].index(old_name)
                                                            st.session_state.resource_groups[group_name][index] = edited_name
                                                
                                                # Сохранить в файл
                                                save_employees_data(
                                                    st.session_state.saved_resources,
                                                    st.session_state.resource_groups
                                                )
                                                st.session_state.editing_employee = None
                                                st.success(f"✓ Сотрудник '{edited_name}' обновлен")
                                                st.rerun()
                                    with cancel_col:
                                        if st.button("❌", key=f"cancel_{idx}", help="Отменить"):
                                            st.session_state.editing_employee = None
                                            st.rerun()
                        else:
                            # Обычное отображение строки сотрудника
                            with st.container():
                                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                                with col1:
                                    st.text(employee_name)
                                with col2:
                                    st.text(employee_max_units)
                                with col3:
                                    if st.button("✏️", key=f"edit_{idx}", help="Редактировать"):
                                        st.session_state.editing_employee = employee_name
                                        st.rerun()
                                with col4:
                                    if st.button("🗑️", key=f"delete_{idx}", help="Удалить"):
                                        st.session_state.delete_employee_name = employee_name
                                        st.rerun()
                else:
                    st.info("Список сотрудников пуст. Добавьте сотрудников через форму ниже или загрузите XML-файл проекта.")
                
                # Добавление нового сотрудника
                st.markdown("---")
                st.markdown("**Добавить нового сотрудника:**")
                with st.expander("➕ Добавить сотрудника", expanded=not st.session_state.saved_resources):
                    new_employee_name = st.text_input("Имя сотрудника:", key="new_employee_name")
                    new_employee_max_units = st.text_input("Max Units:", value="1.0", key="new_employee_max_units")
                    
                    if st.button("💾 Добавить сотрудника", key="add_employee_btn"):
                        if not new_employee_name:
                            st.error("Введите имя сотрудника")
                        else:
                            # Проверить на дубликаты по имени
                            existing_names = [r.get('name') for r in st.session_state.saved_resources]
                            
                            if new_employee_name in existing_names:
                                st.error(f"Сотрудник с именем '{new_employee_name}' уже существует")
                            else:
                                new_employee = {
                                    'name': new_employee_name,
                                    'max_units': new_employee_max_units or '1.0'
                                }
                                st.session_state.saved_resources.append(new_employee)
                                # Сохранить в файл
                                save_employees_data(
                                    st.session_state.saved_resources,
                                    st.session_state.resource_groups
                                )
                                st.success(f"✓ Сотрудник '{new_employee_name}' добавлен")
                                st.rerun()
        
        st.markdown("---")
        
        # Проверка что есть данные для отображения
        if not selected_resources and not display_data:
            st.info("Выберите ресурсы для анализа в табе 'Текущий выбор'")
        else:
            # Суммарный план график
            with st.expander("### 📅 Суммарный план график", expanded=False):
                if st.session_state.parser:
                    # Получить примененную группу, если она есть
                    applied_group_dict = None
                    if hasattr(st.session_state, 'applied_group') and st.session_state.applied_group:
                        group_name, group_resources = st.session_state.applied_group
                        applied_group_dict = {group_name: group_resources}
                    
                    # Получить маппинг parser -> file_name из session_state
                    parser_to_file_name = st.session_state.get('parser_to_file_name', {})
                    
                    # Создать диаграмму Ганта
                    # Использовать workload_data из session_state для единообразия с другими разделами
                    workload_data_for_gantt = st.session_state.get('workload_data')
                    gantt_fig = create_gantt_chart(
                        st.session_state.parser,
                        selected_resources=selected_resources if selected_resources else None,
                        resource_groups=applied_group_dict if applied_group_dict else None,
                        date_range_start=st.session_state.get('date_range_start'),
                        date_range_end=st.session_state.get('date_range_end'),
                        parser_to_file_name=parser_to_file_name if parser_to_file_name else None,
                        workload_data=workload_data_for_gantt
                    )
                    
                    if gantt_fig:
                        st.plotly_chart(gantt_fig, use_container_width=True)
                    else:
                        st.info("Нет задач для отображения в выбранных ресурсах и группах")
                else:
                    st.info("Загрузите файл MS Project для отображения плана графика")
            
            # Таблица анализа рабочей нагрузки
            with st.expander("### 📈 Анализ рабочей нагрузки", expanded=False):
                # Применить MD3 стили для таблиц
                st.markdown(get_md3_table_style(), unsafe_allow_html=True)
                
                # Рассчитать фактические часы для каждого ресурса за период
                actual_hours_dict = {}
                if st.session_state.parser and st.session_state.date_range_start and st.session_state.date_range_end:
                    actual_hours_dict = calculate_actual_hours_per_resource(
                        st.session_state.parser,
                        st.session_state.date_range_start,
                        st.session_state.date_range_end
                    )
                
                # Подготовка датафрейма
                df_data = []
                for item in display_data:
                    percentage = item['workload_percentage']
                    resource_name = item['resource_name']
                    capacity = item['max_capacity']
                    
                    # Получить фактические часы за период
                    actual_hours = actual_hours_dict.get(resource_name, 0.0)
                    
                    # Рассчитать загрузку в часах
                    workload_hours = (capacity * percentage / 100) if capacity > 0 else 0
                    
                    # Индикатор статуса
                    if percentage > 100:
                        status = "🔴 Перегружен"
                        status_color = "#FF4B4B"
                    elif percentage >= 70:
                        status = "🟢 Оптимально"
                        status_color = "#107C10"
                    else:
                        status = "🟡 Недоиспользуется"
                        status_color = "#FFB900"
                    
                    # Формируем строку в зависимости от режима отображения
                    row_data = {
                        'Имя ресурса': resource_name,
                        'Выделено часов': item['total_work_hours'],
                        'Ёмкость часов': capacity,
                        'Рабочие часы за период': actual_hours
                    }
                    
                    # Добавляем колонку загрузки в зависимости от режима
                    if st.session_state.display_mode == 'hours':
                        row_data['Загрузка (часы)'] = workload_hours
                    else:
                        row_data['Нагрузка %'] = percentage
                    
                    row_data['Кол-во задач'] = item['task_count']
                    row_data['Статус'] = status
                    
                    df_data.append(row_data)
                
                df = pd.DataFrame(df_data)
                
                # Сортировка по алфавиту по имени ресурса
                if not df.empty:
                    df = df.sort_values(by='Имя ресурса', key=lambda x: x.str.lower())
                
                # Раскраска датафрейма
                def highlight_workload(row):
                    # Определяем процент в зависимости от режима отображения
                    if st.session_state.display_mode == 'hours':
                        # В режиме часов нужно пересчитать процент из часов
                        capacity = row['Ёмкость часов']
                        if capacity > 0:
                            pct = (row['Загрузка (часы)'] / capacity) * 100
                        else:
                            pct = 0
                    else:
                        pct = row['Нагрузка %']
                    
                    if pct > 100:
                        return ['background-color: #FFE5E5'] * len(row)
                    elif pct < 70:
                        return ['background-color: #FFF4E5'] * len(row)
                    else:
                        return ['background-color: #E5F5E5'] * len(row)
                
                # Форматирование в зависимости от режима
                format_dict = {
                    'Выделено часов': '{:.1f}',
                    'Ёмкость часов': '{:.1f}',
                    'Рабочие часы за период': '{:.1f}'
                }
                
                if st.session_state.display_mode == 'hours':
                    format_dict['Загрузка (часы)'] = '{:.1f}'
                else:
                    format_dict['Нагрузка %'] = '{:.1f}%'
                
                styled_df = df.style.apply(highlight_workload, axis=1).format(format_dict)
                
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Детализация задач
            with st.expander("### 📋 Детализация задач", expanded=False):
                # Сортировка display_data по алфавиту для детализации задач
                sorted_display_data = sorted(display_data, key=lambda x: x['resource_name'].lower())
                for item in sorted_display_data:
                    with st.expander(f"{item['resource_name']} - {item['workload_percentage']:.1f}% нагрузка"):
                        if item['tasks']:
                            task_df = pd.DataFrame(item['tasks'])
                            st.dataframe(task_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Задачи не назначены")
            
            # Рекомендации
            with st.expander("### 💡 Рекомендации", expanded=False):
                # Фильтрация analysis по выбранным ресурсам
                if selected_resources:
                    filtered_analysis = {
                        'overloaded': [r for r in analysis['overloaded'] if r['resource_name'] in selected_resources],
                        'optimal': [r for r in analysis['optimal'] if r['resource_name'] in selected_resources],
                        'underutilized': [r for r in analysis['underutilized'] if r['resource_name'] in selected_resources]
                    }
                else:
                    filtered_analysis = analysis
                
                recommendations = generate_recommendations(filtered_analysis)
                
                if recommendations:
                    for i, rec in enumerate(recommendations, 1):
                        priority_color = {
                            'High': '#FF4B4B',
                            'Medium': '#FFB900',
                            'Low': '#107C10'
                        }.get(rec.get('priority', 'Low'), '#107C10')
                        
                        priority_text = {
                            'High': 'Высокий приоритет',
                            'Medium': 'Средний приоритет',
                            'Low': 'Низкий приоритет'
                        }.get(rec.get('priority', 'Low'), 'Низкий приоритет')
                        
                        if rec['type'] == 'Reassign Tasks':
                            st.markdown(f"""
                            <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                        margin: 10px 0; border-left: 4px solid {priority_color}'>
                                <b>{i}. Перераспределить задачи</b> 
                                <span style='background-color: {priority_color}; color: white; 
                                             padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                    {priority_text}
                                </span><br/>
                                Перенести <b>{rec['hours']:.1f} часов</b> работы от 
                                <b>{rec['from']}</b> к <b>{rec['to']}</b>
                            </div>
                            """, unsafe_allow_html=True)
                        elif rec['type'] == 'Hire Additional Resources':
                            st.markdown(f"""
                            <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                        margin: 10px 0; border-left: 4px solid {priority_color}'>
                                <b>{i}. Нанять дополнительные ресурсы</b>
                                <span style='background-color: {priority_color}; color: white; 
                                             padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                    {priority_text}
                                </span><br/>
                                Рассмотрите найм дополнительных ресурсов для поддержки <b>{rec['resource']}</b><br/>
                                Причина: {rec['reason']}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                        margin: 10px 0; border-left: 4px solid {priority_color}'>
                                <b>{i}. Увеличить использование</b>
                                <span style='background-color: {priority_color}; color: white; 
                                             padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                    {priority_text}
                                </span><br/>
                                <b>{rec['resource']}</b> имеет {rec['available_capacity']} доступной мощности
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.success("✓ Все ресурсы распределены оптимально!")
            
            # Оптимизация с смещением задач
            st.markdown("---")
            st.markdown("## ⚙️ Интеллектуальная оптимизация")
            
            with st.expander("🎯 Настройки оптимизации", expanded=True):
                col_opt1, col_opt2, col_opt3 = st.columns(3)
                
                with col_opt1:
                    max_shift_days = st.slider(
                        "Максимальное смещение задач (дни)",
                        min_value=1,
                        max_value=30,
                        value=14,
                        help="Насколько далеко можно сдвигать задачи для оптимизации"
                    )
                
                with col_opt2:
                    target_load = st.slider(
                        "Целевая загрузка (%)",
                        min_value=70,
                        max_value=100,
                        value=85,
                        help="Желаемый уровень загрузки ресурсов"
                    )
                
                with col_opt3:
                    opt_mode = st.selectbox(
                        "Режим оптимизации",
                        options=['balance', 'minimize_peaks'],
                        format_func=lambda x: 'Балансировка загрузки' if x == 'balance' else 'Минимизация пиков',
                        help="Стратегия оптимизации распределения"
                    )
                
                if st.button("🚀 Запустить оптимизацию", use_container_width=True):
                    with st.spinner("Расчёт оптимального распределения..."):
                        optimization_settings = {
                            'max_shift_days': max_shift_days,
                            'target_load': target_load,
                            'mode': opt_mode
                        }
                        st.session_state.optimization_results = optimize_with_task_shifting(
                            st.session_state.parser, 
                            optimization_settings,
                            st.session_state.date_range_start,
                            st.session_state.date_range_end,
                            selected_resources
                        )
                        st.session_state.timeline_data = st.session_state.parser.get_timeline_workload(
                            st.session_state.date_range_start,
                            st.session_state.date_range_end
                        )
                        st.success("✓ Оптимизация завершена!")
                        st.rerun()
            
            # Показать результаты оптимизации
            if st.session_state.optimization_results:
                st.markdown("### 📈 Предложения по смещению задач")
                
                opt_results = st.session_state.optimization_results
                if opt_results:
                    for i, suggestion in enumerate(opt_results[:10], 1):
                        priority_color = {
                            'Высокий': '#FF4B4B',
                            'Средний': '#FFB900',
                            'Низкий': '#107C10'
                        }.get(suggestion.get('priority', 'Низкий'), '#107C10')
                        
                        improvement_info = f"<b>Улучшение:</b> {suggestion['improvement']}<br/>" if 'improvement' in suggestion else ""
                        st.markdown(f"""
                        <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                    margin: 10px 0; border-left: 4px solid {priority_color}'>
                            <b>{i}. Сдвинуть задачу "{suggestion['task_name']}"</b> 
                            <span style='background-color: {priority_color}; color: white; 
                                         padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                {suggestion['priority']}
                            </span><br/>
                            <b>Ресурс:</b> {suggestion['resource']}<br/>
                            <b>Объём работы:</b> {suggestion['task_hours']:.1f} часов<br/>
                            <b>Текущие даты:</b> {suggestion['original_start']} → {suggestion['original_end']}<br/>
                            <b>Предлагаемые даты:</b> {suggestion['suggested_start']} → {suggestion['suggested_end']} 
                            (сдвиг на {suggestion['shift_days']} дн.)<br/>
                            {improvement_info}
                            <b>Причина:</b> {suggestion['reason']}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("✓ Распределение оптимально, смещения не требуются!")
            
            # Временная загрузка ресурсов
            if st.session_state.timeline_data:
                st.markdown("### 📅 Временная загрузка ресурсов по неделям")
                
                # Фильтрация timeline_data по выбранным ресурсам
                if selected_resources:
                    timeline_data = {k: v for k, v in st.session_state.timeline_data.items() if k in selected_resources}
                else:
                    timeline_data = st.session_state.timeline_data
                
                # Выбор ресурса для детальной визуализации
                sorted_timeline_keys = sorted(timeline_data.keys(), key=str.lower)
                selected_resource_timeline = st.selectbox(
                    "Выберите ресурс для детального анализа",
                    options=sorted_timeline_keys,
                    key="timeline_resource_select"
                )
                
                if selected_resource_timeline and selected_resource_timeline in timeline_data:
                    resource_timeline = timeline_data[selected_resource_timeline]
                    
                    # Получить MD3 цвета для графиков
                    chart_colors = get_md3_chart_colors()
                    color_overloaded = chart_colors['overloaded']
                    color_optimal = chart_colors['optimal']
                    color_underutilized = chart_colors['underutilized']
                    color_primary = chart_colors['optimal']
                    
                    # График временной загрузки
                    fig_timeline = go.Figure()
                    
                    weeks = [w['week'] for w in resource_timeline]
                    percentages = [w['percentage'] for w in resource_timeline]
                    hours = [w['hours'] for w in resource_timeline]
                    
                    # Подготовить данные в зависимости от режима
                    if st.session_state.display_mode == 'hours':
                        y_values = hours
                        text_values = [f"{h:.1f} ч." for h in hours]
                        hover_template = '<b>%{x}</b><br>Загрузка: %{y:.1f} ч.<br><extra></extra>'
                        yaxis_title = "Загрузка (часы)"
                        
                        # Пороговые линии в часах (на основе средней недельной ёмкости)
                        avg_week_capacity = sum(hours) / len(hours) if hours else 40
                        threshold_100 = avg_week_capacity
                        threshold_target = avg_week_capacity * (target_load / 100)
                        line1_text = f"{threshold_100:.1f} ч. (100%)"
                        line2_text = f"{threshold_target:.1f} ч. ({target_load}%)"
                    else:
                        y_values = percentages
                        text_values = [f"{p:.1f}%" for p in percentages]
                        hover_template = '<b>%{x}</b><br>Загрузка: %{y:.1f}%<br>Часов: %{customdata:.1f} ч.<br><extra></extra>'
                        yaxis_title = "Загрузка (%)"
                        threshold_100 = 100
                        threshold_target = target_load
                        line1_text = "100%"
                        line2_text = f"Цель {target_load}%"
                    
                    # Цветовая кодировка по неделям
                    colors_timeline = []
                    for pct in percentages:
                        if pct > 100:
                            colors_timeline.append(color_overloaded)
                        elif pct >= 70:
                            colors_timeline.append(color_optimal)
                        else:
                            colors_timeline.append(color_underutilized)
                    
                    fig_timeline.add_trace(go.Bar(
                        x=weeks,
                        y=y_values,
                        marker_color=colors_timeline,
                        text=text_values,
                        textposition='outside',
                        customdata=hours,
                        hovertemplate=hover_template,
                        name='Загрузка'
                    ))
                    
                    fig_timeline.add_hline(y=threshold_100, line_dash="dash", line_color=color_overloaded, 
                                          annotation_text=line1_text, annotation_position="right")
                    fig_timeline.add_hline(y=threshold_target, line_dash="dot", line_color=color_primary, 
                                          annotation_text=line2_text, annotation_position="right")
                    
                    fig_timeline.update_layout(
                        title=f"Недельная загрузка: {selected_resource_timeline}",
                        xaxis_title="Неделя",
                        yaxis_title=yaxis_title,
                        showlegend=False,
                        height=400,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font=dict(family="Segoe UI, Inter, sans-serif", size=12, color="#323130")
                    )
                    
                    st.plotly_chart(fig_timeline, use_container_width=True)
            
            # Интерактивная замена специалистов
            if filtered_analysis['overloaded']:
                st.markdown("---")
                st.markdown("### 🔄 Интерактивная замена специалистов")
                st.info("Выберите замену для перегруженных специалистов и пересчитайте оптимизацию")
                
                for overloaded_resource in filtered_analysis['overloaded'][:3]:  # Топ-3 перегруженных
                    resource_name = overloaded_resource['resource_name']
                    overload_pct = overloaded_resource['workload_percentage']
                    
                    with st.expander(f"⚠️ {resource_name} ({overload_pct:.1f}% перегрузка)"):
                        st.markdown(f"**Текущая загрузка:** {overload_pct:.1f}%")
                        st.markdown(f"**Избыток:** {overload_pct - 100:.1f}%")
                        
                        # Варианты замены (недоиспользуемые ресурсы)
                        replacement_options = sorted([r['resource_name'] for r in filtered_analysis['underutilized']], key=str.lower)
                        replacement_options.insert(0, "-- Не менять --")
                        
                        selected_replacement = st.selectbox(
                            "Заменить на:",
                            options=replacement_options,
                            key=f"replacement_{resource_name}"
                        )
                        
                        if selected_replacement != "-- Не менять --":
                            if st.button(f"✓ Применить замену {resource_name} → {selected_replacement}", 
                                       key=f"apply_{resource_name}"):
                                st.session_state.resource_replacements[resource_name] = selected_replacement
                                st.success(f"✓ Замена сохранена: {resource_name} → {selected_replacement}")
                                st.info("💡 Запустите оптимизацию заново для пересчёта с учётом замены")
                
                # Показать активные замены
                if st.session_state.resource_replacements:
                    st.markdown("**Активные замены:**")
                    for old_res, new_res in st.session_state.resource_replacements.items():
                        st.markdown(f"- {old_res} → {new_res}")
                    
                    if st.button("🔄 Пересчитать с учётом замен", use_container_width=True):
                        st.info("💡 Функция в разработке: автоматический пересчёт с учётом замен специалистов")
            
            # Опции экспорта
            st.markdown("---")
            st.markdown("### 📥 Экспорт анализа")
            col1, col2 = st.columns(2)
            
            with col1:
                # Рассчитать параметры периода для экспорта
                export_date_start = st.session_state.date_range_start
                export_date_end = st.session_state.date_range_end
                export_business_days = None
                export_capacity = None
                
                if export_date_start and export_date_end:
                    export_business_days = calculate_business_days(export_date_start, export_date_end)
                    export_capacity = calculate_work_capacity(export_business_days)
                
                csv_data = export_to_csv(
                    df, 
                    analysis, 
                    parser=st.session_state.parser,
                    timeline_data=st.session_state.timeline_data,
                    optimization_results=st.session_state.optimization_results,
                    date_start=export_date_start,
                    date_end=export_date_end,
                    business_days=export_business_days,
                    capacity=export_capacity
                )
                st.download_button(
                    label="📄 Скачать CSV",
                    data=csv_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                pdf_data = export_to_pdf(
                    df, 
                    analysis, 
                    recommendations,
                    parser=st.session_state.parser,
                    timeline_data=st.session_state.timeline_data,
                    optimization_results=st.session_state.optimization_results,
                    date_start=export_date_start,
                    date_end=export_date_end,
                    business_days=export_business_days,
                    capacity=export_capacity
                )
                st.download_button(
                    label="📑 Скачать PDF",
                    data=pdf_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Визуализация
            st.markdown("### 📊 Распределение рабочей нагрузки")
            
            # Сортировка display_data по алфавиту для графика
            sorted_display_data = sorted(display_data, key=lambda x: x['resource_name'].lower())
            
            # Получить MD3 цвета для графиков
            chart_colors = get_md3_chart_colors()
            color_overloaded = chart_colors['overloaded']
            color_optimal = chart_colors['optimal']
            color_underutilized = chart_colors['underutilized']
            
            fig = go.Figure()
            
            # Подготовить данные в зависимости от режима отображения
            if st.session_state.display_mode == 'hours':
                # Режим часов
                y_values = [(item['max_capacity'] * item['workload_percentage'] / 100) for item in sorted_display_data]
                text_values = [f"{y:.1f} ч." for y in y_values]
                hover_template = '<b>%{x}</b><br>Загрузка: %{y:.1f} ч.<br><extra></extra>'
                yaxis_title = "Загрузка (часы)"
                
                # Пороговые линии в часах (средняя ёмкость)
                avg_capacity = sum([item['max_capacity'] for item in sorted_display_data]) / len(sorted_display_data) if sorted_display_data else 0
                threshold_100 = avg_capacity
                threshold_70 = avg_capacity * 0.7
                line1_text = f"{threshold_100:.1f} ч. (100%)"
                line2_text = f"{threshold_70:.1f} ч. (70%)"
            else:
                # Режим процентов
                y_values = [item['workload_percentage'] for item in sorted_display_data]
                text_values = [f"{y:.1f}%" for y in y_values]
                hover_template = '<b>%{x}</b><br>Нагрузка: %{y:.1f}%<br><extra></extra>'
                yaxis_title = "Процент нагрузки (%)"
                threshold_100 = 100
                threshold_70 = 70
                line1_text = "100% ёмкость"
                line2_text = "70% порог"
            
            # Цветовая кодировка
            colors_map = []
            for item in sorted_display_data:
                percentage = item['workload_percentage']
                if percentage > 100:
                    colors_map.append(color_overloaded)
                elif percentage >= 70:
                    colors_map.append(color_optimal)
                else:
                    colors_map.append(color_underutilized)
            
            fig.add_trace(go.Bar(
                x=[item['resource_name'] for item in sorted_display_data],
                y=y_values,
                marker_color=colors_map,
                text=text_values,
                textposition='outside',
                hovertemplate=hover_template
            ))
            
            # Добавление пороговых линий
            fig.add_hline(y=threshold_100, line_dash="dash", line_color=color_overloaded, 
                         annotation_text=line1_text, annotation_position="right")
            fig.add_hline(y=threshold_70, line_dash="dash", line_color=color_underutilized, 
                         annotation_text=line2_text, annotation_position="right")
            
            fig.update_layout(
                title="Сравнение рабочей нагрузки ресурсов",
                xaxis_title="Ресурс",
                yaxis_title=yaxis_title,
                showlegend=False,
                height=500,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(family="Segoe UI, Inter, sans-serif", size=12, color="#323130")
            )
            
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor='#E5E5E5')
            
            st.plotly_chart(fig, use_container_width=True)

# Вызов main() для Streamlit - должен выполняться при импорте модуля
# НЕ используем if __name__ == "__main__", потому что Streamlit импортирует модуль
# и __name__ будет "app", а не "__main__"
main()
