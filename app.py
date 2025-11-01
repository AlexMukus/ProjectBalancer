import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
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

# Конфигурация страницы
st.set_page_config(
    page_title="Анализатор управления ресурсами",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Применение MD3 дизайна
st.markdown(get_md3_css(), unsafe_allow_html=True)

# MS Project XML Parser
class MSProjectParser:
    """Парсер для XML-файлов MS Project (.xml, .mspdi)"""
    
    def __init__(self, file_content):
        self.file_content = file_content
        self.tasks = []
        self.resources = []
        self.assignments = []
    
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
            # Очищаем XML от недопустимых символов
            cleaned_content = self.clean_xml_content(self.file_content)
            
            tree = etree.parse(io.BytesIO(cleaned_content))
            root = tree.getroot()
            
            # Получение namespace
            namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
            
            # Парсинг ресурсов
            self.resources = self._parse_resources(root, namespace)
            
            # Парсинг задач
            self.tasks = self._parse_tasks(root, namespace)
            
            # Парсинг назначений
            self.assignments = self._parse_assignments(root, namespace)
            
            return True
        except Exception as e:
            st.error(f"Ошибка при парсинге файла MS Project: {str(e)}")
            return False
    
    def _parse_resources(self, root, namespace):
        """Парсинг информации о ресурсах"""
        resources = []
        resource_elements = root.findall('.//ns:Resource', namespace) if namespace else root.findall('.//Resource')
        
        for resource in resource_elements:
            resource_id = self._get_text(resource, 'ns:UID' if namespace else 'UID', namespace)
            name = self._get_text(resource, 'ns:Name' if namespace else 'Name', namespace)
            
            if resource_id and name:
                resources.append({
                    'id': resource_id,
                    'name': name,
                    'max_units': self._get_text(resource, 'ns:MaxUnits' if namespace else 'MaxUnits', namespace, default='1.0')
                })
        
        return resources
    
    def _parse_tasks(self, root, namespace):
        """Parse task information"""
        tasks = []
        task_elements = root.findall('.//ns:Task', namespace) if namespace else root.findall('.//Task')
        
        for task in task_elements:
            task_id = self._get_text(task, 'ns:UID' if namespace else 'UID', namespace)
            name = self._get_text(task, 'ns:Name' if namespace else 'Name', namespace)
            
            if task_id and name:
                tasks.append({
                    'id': task_id,
                    'name': name,
                    'start': self._get_text(task, 'ns:Start' if namespace else 'Start', namespace),
                    'finish': self._get_text(task, 'ns:Finish' if namespace else 'Finish', namespace),
                    'duration': self._get_text(task, 'ns:Duration' if namespace else 'Duration', namespace),
                    'work': self._get_text(task, 'ns:Work' if namespace else 'Work', namespace)
                })
        
        return tasks
    
    def _parse_assignments(self, root, namespace):
        """Parse resource assignments"""
        assignments = []
        assignment_elements = root.findall('.//ns:Assignment', namespace) if namespace else root.findall('.//Assignment')
        
        for assignment in assignment_elements:
            task_uid = self._get_text(assignment, 'ns:TaskUID' if namespace else 'TaskUID', namespace)
            resource_uid = self._get_text(assignment, 'ns:ResourceUID' if namespace else 'ResourceUID', namespace)
            work = self._get_text(assignment, 'ns:Work' if namespace else 'Work', namespace)
            
            if task_uid and resource_uid:
                assignments.append({
                    'task_id': task_uid,
                    'resource_id': resource_uid,
                    'work': work,
                    'units': self._get_text(assignment, 'ns:Units' if namespace else 'Units', namespace, default='1.0')
                })
        
        return assignments
    
    def _get_text(self, element, tag, namespace, default=''):
        """Helper to get text from XML element"""
        try:
            found = element.find(tag, namespace) if namespace else element.find(tag)
            return found.text if found is not None and found.text else default
        except:
            return default
    
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
        # MS Project model: 1 workday (P1D) = 8 hours
        # Default capacity for resources is 8 hours per workday
        if range_start_dt and range_end_dt:
            range_duration = range_end_dt - range_start_dt
            calendar_days = range_duration.total_seconds() / (24 * 3600)
            
            if calendar_days <= 0:
                # Minimum: 1 workday
                available_work_hours_base = 8
            else:
                # Count workdays (approximate: 5/7 of calendar days are workdays)
                workdays = calendar_days * (5.0 / 7.0)
                # 8 hours per workday
                available_work_hours_base = workdays * 8
        else:
            # Default: 4 weeks = 20 workdays = 160 hours
            available_work_hours_base = 160
        
        for resource in self.resources:
            # Get all assignments for this resource
            resource_assignments = [a for a in self.assignments if a['resource_id'] == resource['id']]
            
            # Calculate total work hours (only within date range)
            total_work_hours = 0
            task_details = []
            
            for assignment in resource_assignments:
                # Get task info
                task = next((t for t in self.tasks if t['id'] == assignment['task_id']), None)
                if task and task['start'] and task['finish']:
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
        """Parse date string to datetime object"""
        if not date_string:
            return None
        
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            try:
                # Try common MS Project formats
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(date_string, fmt)
                    except:
                        continue
            except:
                pass
        
        return None
    
    def _parse_work_hours(self, work_string):
        """Parse work hours from MS Project ISO-8601 duration format (e.g., PT8H0M0S, P2DT4H0M0S)"""
        if not work_string:
            return 0
        
        try:
            # MS Project uses ISO-8601 duration format: P[n]DT[n]H[n]M[n]S
            # P2DT4H30M0S = 2 days, 4 hours, 30 minutes
            hours = 0
            
            if work_string.startswith('P'):
                # Extract days (assuming 8-hour workdays)
                if 'D' in work_string:
                    d_start = 1  # After 'P'
                    d_end = work_string.index('D')
                    days = float(work_string[d_start:d_end])
                    hours += days * 8  # 8-hour workday
                
                # Extract hours
                if 'H' in work_string:
                    # Find start position (after 'T' or 'D')
                    if 'T' in work_string:
                        h_start = work_string.index('T') + 1
                    else:
                        h_start = work_string.index('D') + 1
                    h_end = work_string.index('H')
                    # Extract the number between start and 'H'
                    h_str = work_string[h_start:h_end]
                    # Remove any non-digit characters except '.'
                    h_str = ''.join(c for c in h_str if c.isdigit() or c == '.')
                    if h_str:
                        hours += float(h_str)
                
                # Extract minutes
                if 'M' in work_string and 'T' in work_string:
                    m_start = work_string.index('H') + 1 if 'H' in work_string else work_string.index('T') + 1
                    m_end = work_string.index('M')
                    m_str = work_string[m_start:m_end]
                    m_str = ''.join(c for c in m_str if c.isdigit() or c == '.')
                    if m_str:
                        minutes = float(m_str)
                        hours += minutes / 60
                
                return hours
            else:
                # Try to parse as number
                return float(work_string)
        except Exception as e:
            # Fallback to 0 if parsing fails
            return 0
    
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
        
        # Кэшировать задачи для быстрого доступа
        task_dict = {t['id']: t for t in self.tasks}
        
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
            resource_assignments = [a for a in self.assignments if a['resource_id'] == resource['id']]
            weekly_loads = []
            
            for week in weeks:
                week_hours = 0
                
                for assignment in resource_assignments:
                    task = task_dict.get(assignment['task_id'])  # Использовать кэш
                    if task and task['start'] and task['finish']:
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
    
    # Получить временную загрузку и кэш задач с учётом диапазона
    timeline_data = parser.get_timeline_workload(date_range_start, date_range_end)
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
        
        resource_assignments = [a for a in parser.assignments if a['resource_id'] == resource['id']]
        
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
                task = task_dict.get(assignment['task_id'])
                if not task or not task['start'] or not task['finish']:
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
            
            # Попробовать сдвинуть задачи в недозагруженные периоды
            for task_info in sorted(tasks_in_week, key=lambda x: x['hours'], reverse=True):
                task = task_info['task']
                task_start = task_info['start']
                task_end = task_info['end']
                task_hours = task_info['hours']
                
                best_shift = None
                best_improvement = 0
                
                # Проверить все возможные сдвиги
                for shift_days in range(1, max_shift + 1):
                    new_start = task_start + timedelta(days=shift_days)
                    new_end = task_end + timedelta(days=shift_days)
                    
                    # Найти все недели, в которые попадёт сдвинутая задача
                    overlapping_weeks = []
                    for week_info in weeks_with_dates:
                        overlap_start = max(new_start, week_info['start'])
                        overlap_end = min(new_end, week_info['end'])
                        
                        if overlap_start <= overlap_end:
                            # Рассчитать долю задачи в этой неделе
                            task_duration_days = (task_end - task_start).days + 1
                            overlap_days = (overlap_end - overlap_start).days + 1
                            proportion = overlap_days / task_duration_days if task_duration_days > 0 else 0
                            hours_in_week = task_hours * proportion
                            
                            overlapping_weeks.append({
                                'index': week_info['index'],
                                'hours': hours_in_week,
                                'proportion': proportion
                            })
                    
                    if not overlapping_weeks:
                        continue
                    
                    # Выбрать основную целевую неделю (с наибольшей долей задачи)
                    main_target = max(overlapping_weeks, key=lambda w: w['proportion'])
                    target_week_idx = main_target['index']
                    
                    if target_week_idx == week_idx or target_week_idx >= len(weekly_loads):
                        continue
                    
                    # Проверить, что целевая неделя менее загружена
                    target_week = weekly_loads[target_week_idx]
                    
                    # Рассчитать реальное улучшение в часах
                    # Сколько часов освободится в исходной неделе
                    hours_removed_from_source = task_hours  # Упрощение: вся задача уходит
                    # Сколько часов добавится в целевую неделю
                    hours_added_to_target = main_target['hours']
                    
                    # Проверить, что сдвиг действительно снижает перегрузку
                    new_source_hours = week_data['hours'] - hours_removed_from_source
                    new_source_percentage = (new_source_hours / week_data['capacity']) * 100 if week_data['capacity'] > 0 else 0
                    
                    new_target_hours = target_week['hours'] + hours_added_to_target
                    new_target_percentage = (new_target_hours / target_week['capacity']) * 100 if target_week['capacity'] > 0 else 0
                    
                    # Условия: исходная неделя становится менее перегруженной, целевая не становится перегруженной
                    if new_source_percentage < week_data['percentage'] and new_target_percentage <= 100:
                        # Оценить улучшение как снижение перегрузки
                        improvement = week_data['percentage'] - new_source_percentage
                        
                        if improvement > best_improvement:
                            best_improvement = improvement
                            best_shift = shift_days
                
                # Если нашли хороший сдвиг, добавляем рекомендацию
                if best_shift:
                    new_start = task_start + timedelta(days=best_shift)
                    new_end = task_end + timedelta(days=best_shift)
                    
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
                        'reason': f'Снизить перегрузку на {excess_hours:.1f}ч в неделю {week_data["week"]}',
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
            resource_assignments = [a for a in parser.assignments if a['resource_id'] == resource['id']]
            
            for assignment in resource_assignments:
                task = next((t for t in parser.tasks if t['id'] == assignment['task_id']), None)
                if task:
                    task_id = task.get('id', '')
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
            resource_assignments = [a for a in parser.assignments if a['resource_id'] == resource['id']]
            
            for assignment in resource_assignments[:5]:  # До 5 задач на ресурс
                if task_count >= max_tasks:
                    break
                task = next((t for t in parser.tasks if t['id'] == assignment['task_id']), None)
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

def calculate_business_days(start_date, end_date):
    """Рассчитывает количество рабочих дней между двумя датами (исключая субботу и воскресенье)"""
    if not start_date or not end_date:
        return 0
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday
        if current_date.weekday() < 5:  # 0-4 это пн-пт
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def calculate_work_capacity(business_days):
    """Рассчитывает рабочую емкость одного человека в часах (дни × 8 часов)"""
    return business_days * 8

def calculate_actual_hours_per_resource(parser, date_start, date_end):
    """Рассчитывает фактические рабочие часы для каждого ресурса за указанный период"""
    if not parser:
        return {}
    
    resource_hours = {}
    
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
        
        # Найти все назначения для этой задачи
        task_assignments = [a for a in parser.assignments if a['task_id'] == task['id']]
        
        for assignment in task_assignments:
            resource_id = assignment.get('resource_id')
            if not resource_id:
                continue
                
            # Найти имя ресурса
            resource = next((r for r in parser.resources if r['id'] == resource_id), None)
            if not resource:
                continue
                
            resource_name = resource['name']
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
if 'resource_groups' not in st.session_state:
    st.session_state.resource_groups = {}
if 'display_mode' not in st.session_state:
    st.session_state.display_mode = 'percentage'  # По умолчанию проценты

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
        
        st.markdown("### 📁 Загрузка файла MS Project")
        st.markdown("Поддерживаемые форматы: .xml, .mspdi")
        st.info("💡 Чтобы экспортировать .mpp в XML: в MS Project выберите Файл → Сохранить как → выберите Формат XML (*.xml)")
        
        uploaded_file = st.file_uploader(
            "Выберите файл",
            type=['xml', 'mspdi'],
            help="Загрузите ваш XML-файл Microsoft Project"
        )
        
        # Сохранить содержимое файла как байты для надежности при st.rerun()
        if uploaded_file is not None:
            st.session_state.uploaded_file_content = uploaded_file.getvalue()
            st.session_state.uploaded_file_name = uploaded_file.name
        
        # Проверить наличие загруженного файла
        has_file = (uploaded_file is not None) or ('uploaded_file_content' in st.session_state)
        
        if has_file:
            file_name = uploaded_file.name if uploaded_file is not None else st.session_state.get('uploaded_file_name', 'файл')
            st.success(f"✓ {file_name} загружен")
            
            if st.button("🔄 Анализировать файл", use_container_width=True):
                with st.spinner("Анализ файла MS Project..."):
                    # Использовать сохраненное содержимое или прочитать новый файл
                    if uploaded_file is not None:
                        file_content = uploaded_file.getvalue()
                    else:
                        file_content = st.session_state.uploaded_file_content
                    
                    parser = MSProjectParser(file_content)
                    
                    if parser.parse():
                        st.session_state.parser = parser
                        # Инициализировать даты проекта на основе текущей даты
                        today = datetime.now().date()
                        
                        # Получить даты проекта для ограничения
                        project_start, project_end = parser.get_project_dates()
                        
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
                        st.session_state.workload_data = parser.get_resource_workload_data(
                            st.session_state.date_range_start,
                            st.session_state.date_range_end
                        )
                        st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                        st.success("✓ Файл успешно проанализирован!")
                        st.rerun()
                    else:
                        st.error("Не удалось проанализировать файл")
        
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
            
            # Material Design 3 панель управления периодом
            period_str = f"{st.session_state.date_range_start.strftime('%d.%m.%Y')} - {st.session_state.date_range_end.strftime('%d.%m.%Y')}"
            st.markdown(md3_info_panel(period_str, business_days, work_capacity), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Объединенная секция управления персоналом
        st.markdown("### 👥 Управление персоналом")
        
        # Инициализация applied_group если нужно
        if not hasattr(st.session_state, 'applied_group'):
            st.session_state.applied_group = None
        
        # Инициализация переменных для использования вне табов
        selected_resources = []
        display_data = workload_data
        
        # Два таба: Текущий выбор и Сохраненные группы
        tab1, tab2 = st.tabs(["🔍 Текущий выбор", "💾 Сохраненные группы"])
        
        # ========== ТАБ 1: ТЕКУЩИЙ ВЫБОР ==========
        with tab1:
            all_names = [item['resource_name'] for item in workload_data]
            
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
            
            if not filtered_data:
                st.warning("Ресурсы, соответствующие вашему запросу, не найдены.")
                selected_resources = []
                display_data = []
            else:
                # Определить default значения для multiselect
                if st.session_state.applied_group:
                    # Группа применена: использовать ресурсы из группы как default (но не ограничивать options)
                    group_name, group_resources = st.session_state.applied_group
                    st.info(f"📌 Применена группа '{group_name}' ({len(group_resources)} чел.). Вы можете добавить дополнительные ресурсы из списка ниже.")
                    # Default - только ресурсы из группы, которые есть в filtered_data
                    default_resources = [name for name in group_resources 
                                       if name in [item['resource_name'] for item in filtered_data]]
                else:
                    # Группа не применена: выбрать всех из filtered_data
                    default_resources = [item['resource_name'] for item in filtered_data]
                
                # Множественный выбор - options всегда содержат ВСЕ ресурсы из filtered_data
                selected_resources = st.multiselect(
                    "Выберите конкретные ресурсы для анализа:",
                    options=[item['resource_name'] for item in filtered_data],
                    default=default_resources,
                    key="current_selection_multiselect"
                )
                
                # НОВАЯ ФУНКЦИЯ: Быстрое сохранение текущего выбора как группы
                if selected_resources and len(selected_resources) > 0:
                    st.markdown("---")
                    with st.expander("💾 Сохранить текущий выбор как группу"):
                        quick_group_name = st.text_input(
                            "Название новой группы:",
                            placeholder="например, Команда А",
                            key="quick_save_group_name"
                        )
                        if st.button("💾 Сохранить", key="quick_save_btn"):
                            if not quick_group_name:
                                st.error("Введите название группы")
                            elif quick_group_name in st.session_state.resource_groups:
                                st.error("Группа с таким названием уже существует")
                            else:
                                st.session_state.resource_groups[quick_group_name] = selected_resources.copy()
                                st.success(f"✓ Группа '{quick_group_name}' создана ({len(selected_resources)} чел.)")
                                st.rerun()
                
                if selected_resources:
                    display_data = [item for item in filtered_data 
                                  if item['resource_name'] in selected_resources]
                else:
                    display_data = filtered_data
        
        # ========== ТАБ 2: СОХРАНЕННЫЕ ГРУППЫ ==========
        with tab2:
            # Выбор и применение сохраненной группы
            if st.session_state.resource_groups:
                st.markdown("**Применить сохраненную группу:**")
                group_names = ["-- Не выбрано --"] + list(st.session_state.resource_groups.keys())
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
                        st.success(f"✓ Группа '{selected_group}' применена ({len(group_resources)} чел.)")
                        st.rerun()
                
                st.markdown("---")
            else:
                st.info("У вас пока нет сохраненных групп. Создайте новую ниже.")
            
            # Создание новой группы с нуля
            st.markdown("**Создать новую группу:**")
            with st.expander("➕ Создать группу", expanded=not st.session_state.resource_groups):
                new_group_name = st.text_input("Название группы:", placeholder="например, Разработчики", key="new_group_name_input")
                
                all_names = [item['resource_name'] for item in workload_data]
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
                            st.success(f"✓ Группа '{group_name}' удалена")
                            st.rerun()
                    
                    # Expander с полным составом группы
                    with st.expander(f"👁️ Просмотр состава группы '{group_name}'"):
                        if len(group_members) > 0:
                            # Вывести всех участников в виде нумерованного списка
                            for idx, member in enumerate(group_members, 1):
                                st.text(f"{idx}. {member}")
                        else:
                            st.caption("Группа пуста")
                    
                    st.markdown("")  # Добавить отступ между группами
        
        st.markdown("---")
        
        # Проверка что есть данные для отображения
        if not selected_resources and not display_data:
            st.info("Выберите ресурсы для анализа в табе 'Текущий выбор'")
        else:
            # Таблица анализа рабочей нагрузки
            st.markdown("### 📈 Анализ рабочей нагрузки")
            
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
            st.markdown("### 📋 Детализация задач")
            
            for item in display_data:
                with st.expander(f"{item['resource_name']} - {item['workload_percentage']:.1f}% нагрузка"):
                    if item['tasks']:
                        task_df = pd.DataFrame(item['tasks'])
                        st.dataframe(task_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Задачи не назначены")
            
            # Рекомендации
            st.markdown("### 💡 Рекомендации")
            
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
                selected_resource_timeline = st.selectbox(
                    "Выберите ресурс для детального анализа",
                    options=list(timeline_data.keys()),
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
                        replacement_options = [r['resource_name'] for r in filtered_analysis['underutilized']]
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
            
            # Получить MD3 цвета для графиков
            chart_colors = get_md3_chart_colors()
            color_overloaded = chart_colors['overloaded']
            color_optimal = chart_colors['optimal']
            color_underutilized = chart_colors['underutilized']
            
            fig = go.Figure()
            
            # Подготовить данные в зависимости от режима отображения
            if st.session_state.display_mode == 'hours':
                # Режим часов
                y_values = [(item['max_capacity'] * item['workload_percentage'] / 100) for item in display_data]
                text_values = [f"{y:.1f} ч." for y in y_values]
                hover_template = '<b>%{x}</b><br>Загрузка: %{y:.1f} ч.<br><extra></extra>'
                yaxis_title = "Загрузка (часы)"
                
                # Пороговые линии в часах (средняя ёмкость)
                avg_capacity = sum([item['max_capacity'] for item in display_data]) / len(display_data) if display_data else 0
                threshold_100 = avg_capacity
                threshold_70 = avg_capacity * 0.7
                line1_text = f"{threshold_100:.1f} ч. (100%)"
                line2_text = f"{threshold_70:.1f} ч. (70%)"
            else:
                # Режим процентов
                y_values = [item['workload_percentage'] for item in display_data]
                text_values = [f"{y:.1f}%" for y in y_values]
                hover_template = '<b>%{x}</b><br>Нагрузка: %{y:.1f}%<br><extra></extra>'
                yaxis_title = "Процент нагрузки (%)"
                threshold_100 = 100
                threshold_70 = 70
                line1_text = "100% ёмкость"
                line2_text = "70% порог"
            
            # Цветовая кодировка
            colors_map = []
            for item in display_data:
                percentage = item['workload_percentage']
                if percentage > 100:
                    colors_map.append(color_overloaded)
                elif percentage >= 70:
                    colors_map.append(color_optimal)
                else:
                    colors_map.append(color_underutilized)
            
            fig.add_trace(go.Bar(
                x=[item['resource_name'] for item in display_data],
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

if __name__ == "__main__":
    main()
