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

# Конфигурация страницы
st.set_page_config(
    page_title="Анализатор управления ресурсами",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Microsoft-inspired styling
st.markdown("""
<style>
    /* Color scheme variables */
    :root {
        --primary-blue: #0078D4;
        --success-green: #107C10;
        --warning-red: #FF4B4B;
        --background-grey: #F3F2F1;
        --text-charcoal: #323130;
        --accent-purple: #5C2E91;
        --warning-yellow: #FFB900;
    }
    
    /* Main styling */
    .stApp {
        background-color: var(--background-grey);
    }
    
    /* Headers */
    h1, h2, h3 {
        color: var(--text-charcoal);
        font-family: 'Segoe UI', 'Inter', sans-serif;
    }
    
    /* Metric cards */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    /* Status badges */
    .status-overloaded {
        background-color: #FF4B4B;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .status-optimal {
        background-color: #107C10;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .status-underutilized {
        background-color: #FFB900;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: var(--primary-blue);
        color: white;
        border-radius: 4px;
        border: none;
        padding: 8px 16px;
        font-weight: 500;
    }
    
    .stButton > button:hover {
        background-color: #005A9E;
    }
    
    /* Data tables */
    .dataframe {
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 14px;
    }
    
    /* File uploader */
    .uploadedFile {
        border-color: var(--primary-blue);
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: white;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

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
    
    def get_resource_workload_data(self):
        """Calculate workload data for each resource"""
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
        
        # Calculate total available work hours for the project
        # MS Project model: 1 workday (P1D) = 8 hours
        # Default capacity for resources is 8 hours per workday
        if project_start and project_end:
            project_duration = project_end - project_start
            calendar_days = project_duration.total_seconds() / (24 * 3600)
            
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
            
            # Calculate total work hours
            total_work_hours = 0
            task_details = []
            
            for assignment in resource_assignments:
                # Get task info
                task = next((t for t in self.tasks if t['id'] == assignment['task_id']), None)
                if task:
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
    
    def get_timeline_workload(self):
        """Рассчитать временную загрузку ресурсов по неделям"""
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
        
        if not project_start or not project_end:
            return {}
        
        # Кэшировать задачи для быстрого доступа
        task_dict = {t['id']: t for t in self.tasks}
        
        # Создать недельные периоды
        current_date = project_start
        weeks = []
        while current_date <= project_end:
            week_end = current_date + timedelta(days=6)
            weeks.append({
                'start': current_date,
                'end': min(week_end, project_end),
                'label': f"{current_date.strftime('%d.%m')} - {min(week_end, project_end).strftime('%d.%m')}"
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
                    'hours': week_hours,
                    'capacity': week_capacity,
                    'percentage': week_percentage
                })
            
            timeline_data[resource['name']] = weekly_loads
        
        return timeline_data

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

def optimize_with_task_shifting(parser, settings):
    """
    Оптимизация распределения с смещением задач во времени
    
    settings = {
        'max_shift_days': int,  # Максимальное смещение задач в днях
        'target_load': float,   # Целевая загрузка (70-100%)
        'mode': 'balance'       # Режим: 'balance' или 'minimize_peaks'
    }
    """
    max_shift = settings.get('max_shift_days', 14)
    target_load = settings.get('target_load', 85)
    mode = settings.get('mode', 'balance')
    
    # Получить временную загрузку и кэш задач
    timeline_data = parser.get_timeline_workload()
    task_dict = {t['id']: t for t in parser.tasks}
    
    # Найти перегруженные периоды для каждого ресурса
    optimization_suggestions = []
    
    for resource_name, weekly_loads in timeline_data.items():
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
        
        if not project_start or not project_end:
            continue
            
        current_date = project_start
        weeks_with_dates = []
        while current_date <= project_end:
            week_end = current_date + timedelta(days=6)
            weeks_with_dates.append({
                'start': current_date,
                'end': min(week_end, project_end),
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

def export_to_csv(workload_df, analysis):
    """Export analysis to CSV"""
    csv_buffer = io.StringIO()
    workload_df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

def export_to_pdf(workload_df, analysis, recommendations):
    """Экспорт анализа в PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Заголовок
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0078D4'),
        spaceAfter=30
    )
    elements.append(Paragraph("Отчёт по анализу рабочей нагрузки ресурсов", title_style))
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
    table_data = [['Ресурс', 'Выделено', 'Ёмкость', 'Нагрузка %', 'Задачи', 'Статус']]
    
    for _, row in workload_df.iterrows():
        status = 'Перегружен' if row['Нагрузка %'] > 100 else ('Оптимально' if row['Нагрузка %'] >= 70 else 'Недоиспользуется')
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
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Рекомендации
    if recommendations:
        elements.append(Paragraph("<b>Рекомендации</b>", styles['Heading2']))
        for i, rec in enumerate(recommendations[:10], 1):
            if rec['type'] == 'Reassign Tasks':
                rec_text = f"{i}. Перераспределить задачи - Перенести {rec['hours']:.1f}ч от {rec['from']} к {rec['to']}"
            elif rec['type'] == 'Hire Additional Resources':
                rec_text = f"{i}. Нанять дополнительные ресурсы для {rec['resource']}: {rec['reason']}"
            else:
                rec_text = f"{i}. Увеличить использование {rec['resource']}: {rec['available_capacity']}"
            elements.append(Paragraph(rec_text, styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

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
        st.markdown("### 📁 Загрузка файла MS Project")
        st.markdown("Поддерживаемые форматы: .xml, .mspdi")
        st.info("💡 Чтобы экспортировать .mpp в XML: в MS Project выберите Файл → Сохранить как → выберите Формат XML (*.xml)")
        
        uploaded_file = st.file_uploader(
            "Выберите файл",
            type=['xml', 'mspdi'],
            help="Загрузите ваш XML-файл Microsoft Project"
        )
        
        if uploaded_file:
            st.success(f"✓ {uploaded_file.name} загружен")
            
            if st.button("🔄 Анализировать файл", use_container_width=True):
                with st.spinner("Анализ файла MS Project..."):
                    file_content = uploaded_file.read()
                    parser = MSProjectParser(file_content)
                    
                    if parser.parse():
                        st.session_state.parser = parser
                        st.session_state.workload_data = parser.get_resource_workload_data()
                        st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                        st.success("✓ Файл успешно проанализирован!")
                        st.rerun()
                    else:
                        st.error("Не удалось проанализировать файл")
        
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
        
        st.markdown("---")
        
        # Поиск персонала
        st.markdown("### 🔍 Фильтр по персоналу")
        all_names = [item['resource_name'] for item in workload_data]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("Поиск по фамилии или имени:", placeholder="например, Иванов")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            show_all = st.checkbox("Показать всех", value=True)
        
        # Filter data
        if show_all or not search_term:
            filtered_data = workload_data
        else:
            filtered_data = [item for item in workload_data 
                           if search_term.lower() in item['resource_name'].lower()]
        
        if not filtered_data:
            st.warning("Ресурсы, соответствующие вашему запросу, не найдены.")
        else:
            # Множественный выбор
            selected_resources = st.multiselect(
                "Выберите конкретные ресурсы для анализа:",
                options=[item['resource_name'] for item in filtered_data],
                default=[item['resource_name'] for item in filtered_data]
            )
            
            if selected_resources:
                display_data = [item for item in filtered_data 
                              if item['resource_name'] in selected_resources]
            else:
                display_data = filtered_data
            
            # Таблица анализа рабочей нагрузки
            st.markdown("### 📈 Анализ рабочей нагрузки")
            
            # Подготовка датафрейма
            df_data = []
            for item in display_data:
                percentage = item['workload_percentage']
                
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
                
                df_data.append({
                    'Имя ресурса': item['resource_name'],
                    'Выделено часов': item['total_work_hours'],
                    'Ёмкость часов': item['max_capacity'],
                    'Нагрузка %': percentage,
                    'Кол-во задач': item['task_count'],
                    'Статус': status
                })
            
            df = pd.DataFrame(df_data)
            
            # Раскраска датафрейма
            def highlight_workload(row):
                if row['Нагрузка %'] > 100:
                    return ['background-color: #FFE5E5'] * len(row)
                elif row['Нагрузка %'] < 70:
                    return ['background-color: #FFF4E5'] * len(row)
                else:
                    return ['background-color: #E5F5E5'] * len(row)
            
            styled_df = df.style.apply(highlight_workload, axis=1).format({
                'Выделено часов': '{:.1f}',
                'Ёмкость часов': '{:.1f}',
                'Нагрузка %': '{:.1f}%'
            })
            
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
            
            recommendations = generate_recommendations(analysis)
            
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
                            optimization_settings
                        )
                        st.session_state.timeline_data = st.session_state.parser.get_timeline_workload()
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
                
                timeline_data = st.session_state.timeline_data
                
                # Выбор ресурса для детальной визуализации
                selected_resource_timeline = st.selectbox(
                    "Выберите ресурс для детального анализа",
                    options=list(timeline_data.keys()),
                    key="timeline_resource_select"
                )
                
                if selected_resource_timeline and selected_resource_timeline in timeline_data:
                    resource_timeline = timeline_data[selected_resource_timeline]
                    
                    # График временной загрузки
                    fig_timeline = go.Figure()
                    
                    weeks = [w['week'] for w in resource_timeline]
                    percentages = [w['percentage'] for w in resource_timeline]
                    hours = [w['hours'] for w in resource_timeline]
                    
                    # Цветовая кодировка по неделям
                    colors_timeline = []
                    for pct in percentages:
                        if pct > 100:
                            colors_timeline.append('#FF4B4B')
                        elif pct >= 70:
                            colors_timeline.append('#107C10')
                        else:
                            colors_timeline.append('#FFB900')
                    
                    fig_timeline.add_trace(go.Bar(
                        x=weeks,
                        y=percentages,
                        marker_color=colors_timeline,
                        text=[f"{p:.1f}%" for p in percentages],
                        textposition='outside',
                        hovertemplate='<b>%{x}</b><br>Загрузка: %{y:.1f}%<br>Часов: ' + 
                                     '<br>'.join([f"{h:.1f}" for h in hours]) + '<br><extra></extra>',
                        name='Загрузка'
                    ))
                    
                    fig_timeline.add_hline(y=100, line_dash="dash", line_color="#FF4B4B", 
                                          annotation_text="100%", annotation_position="right")
                    fig_timeline.add_hline(y=target_load, line_dash="dot", line_color="#0078D4", 
                                          annotation_text=f"Цель {target_load}%", annotation_position="right")
                    
                    fig_timeline.update_layout(
                        title=f"Недельная загрузка: {selected_resource_timeline}",
                        xaxis_title="Неделя",
                        yaxis_title="Загрузка (%)",
                        showlegend=False,
                        height=400,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font=dict(family="Segoe UI, Inter, sans-serif", size=12, color="#323130")
                    )
                    
                    st.plotly_chart(fig_timeline, use_container_width=True)
            
            # Интерактивная замена специалистов
            if analysis['overloaded']:
                st.markdown("---")
                st.markdown("### 🔄 Интерактивная замена специалистов")
                st.info("Выберите замену для перегруженных специалистов и пересчитайте оптимизацию")
                
                for overloaded_resource in analysis['overloaded'][:3]:  # Топ-3 перегруженных
                    resource_name = overloaded_resource['resource_name']
                    overload_pct = overloaded_resource['workload_percentage']
                    
                    with st.expander(f"⚠️ {resource_name} ({overload_pct:.1f}% перегрузка)"):
                        st.markdown(f"**Текущая загрузка:** {overload_pct:.1f}%")
                        st.markdown(f"**Избыток:** {overload_pct - 100:.1f}%")
                        
                        # Варианты замены (недоиспользуемые ресурсы)
                        replacement_options = [r['resource_name'] for r in analysis['underutilized']]
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
                csv_data = export_to_csv(df, analysis)
                st.download_button(
                    label="📄 Скачать CSV",
                    data=csv_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                pdf_data = export_to_pdf(df, analysis, recommendations)
                st.download_button(
                    label="📑 Скачать PDF",
                    data=pdf_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Визуализация
            st.markdown("### 📊 Распределение рабочей нагрузки")
            
            fig = go.Figure()
            
            # Add bars
            colors_map = []
            for item in display_data:
                percentage = item['workload_percentage']
                if percentage > 100:
                    colors_map.append('#FF4B4B')
                elif percentage >= 70:
                    colors_map.append('#107C10')
                else:
                    colors_map.append('#FFB900')
            
            fig.add_trace(go.Bar(
                x=[item['resource_name'] for item in display_data],
                y=[item['workload_percentage'] for item in display_data],
                marker_color=colors_map,
                text=[f"{item['workload_percentage']:.1f}%" for item in display_data],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Workload: %{y:.1f}%<br><extra></extra>'
            ))
            
            # Добавление пороговых линий
            fig.add_hline(y=100, line_dash="dash", line_color="#FF4B4B", 
                         annotation_text="100% ёмкость", annotation_position="right")
            fig.add_hline(y=70, line_dash="dash", line_color="#FFB900", 
                         annotation_text="70% порог", annotation_position="right")
            
            fig.update_layout(
                title="Сравнение рабочей нагрузки ресурсов",
                xaxis_title="Ресурс",
                yaxis_title="Процент нагрузки (%)",
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
