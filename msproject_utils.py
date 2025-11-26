"""
Модуль утилит для работы с MS Project XML файлами
Содержит общие функции для парсинга и обработки данных
"""
import logging
from datetime import datetime, timedelta


# ============================================================================
# Настройка логирования
# ============================================================================

def setup_logger(name):
    """
    Настраивает и возвращает logger для модуля
    
    Args:
        name: Имя модуля для logger
        
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(name)s - %(levelname)s - %(message)s'
        )
    return logger


# ============================================================================
# Работа с XML и namespace
# ============================================================================

def get_namespace(root):
    """
    Извлекает namespace из корневого элемента XML
    
    Args:
        root: Корневой элемент XML дерева
        
    Returns:
        Словарь namespace или пустой словарь
    """
    return {'ns': root.nsmap[None]} if None in root.nsmap else {}


def make_tag(tag, namespace):
    """
    Формирует тег с учетом namespace
    
    Args:
        tag: Базовое имя тега (без префикса)
        namespace: Словарь namespace или пустой словарь
        
    Returns:
        Тег с префиксом namespace или без него
    """
    return f'ns:{tag}' if namespace else tag


def find_elements(root, tag, namespace):
    """
    Находит элементы в XML с учетом namespace
    
    Args:
        root: Корневой элемент XML дерева
        tag: Базовое имя тега (без префикса)
        namespace: Словарь namespace или пустой словарь
        
    Returns:
        Список найденных элементов
    """
    tag_with_ns = make_tag(tag, namespace)
    if namespace:
        return root.findall(f'.//{tag_with_ns}', namespace)
    else:
        return root.findall(f'.//{tag}')


def get_text(element, tag, namespace, default=''):
    """
    Вспомогательная функция для извлечения текста из XML элемента
    
    Args:
        element: XML элемент
        tag: Тег для поиска (с или без namespace префикса)
        namespace: Словарь namespace или пустой словарь
        default: Значение по умолчанию, если элемент не найден
    
    Returns:
        Текст элемента или значение по умолчанию
    """
    logger = logging.getLogger(__name__)
    try:
        found = element.find(tag, namespace) if namespace else element.find(tag)
        if found is not None and found.text:
            return found.text.strip() if found.text else default
        return default
    except Exception as e:
        logger.debug(f"Ошибка при извлечении текста из тега '{tag}': {e}")
        return default


# ============================================================================
# Парсинг дат и времени
# ============================================================================

def parse_date(date_string):
    """
    Парсит строку даты в datetime объект
    
    Поддерживает форматы:
    - ISO 8601: '2024-01-15T10:30:00', '2024-01-15T10:30:00Z'
    - MS Project: '2024-01-15T10:30:00', '2024-01-15 10:30:00', '2024-01-15'
    
    Args:
        date_string: Строка с датой
        
    Returns:
        datetime объект или None если парсинг не удался
    """
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


# ============================================================================
# Парсинг рабочих часов (ISO-8601 duration)
# ============================================================================

def parse_work_hours(work_string):
    """
    Парсит рабочие часы из MS Project ISO-8601 duration формата
    
    Форматы:
    - PT8H0M0S = 8 hours
    - P2DT4H30M0S = 2 days (16 hours) + 4 hours + 30 minutes = 20.5 hours
    - P1D = 1 day = 8 hours (стандартный рабочий день)
    
    Args:
        work_string: Строка в формате ISO-8601 duration или число
        
    Returns:
        Количество часов (float) или 0 если парсинг не удался
    """
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
        logger = logging.getLogger(__name__)
        logger.debug(f"Ошибка при парсинге рабочих часов '{work_string}': {e}")
        return 0


# ============================================================================
# Расчет рабочих дней и емкости
# ============================================================================

def calculate_business_days(start_date, end_date):
    """
    Рассчитывает количество рабочих дней между двумя датами
    (исключая субботу и воскресенье)
    
    Args:
        start_date: Начальная дата (datetime.date или datetime)
        end_date: Конечная дата (datetime.date или datetime)
        
    Returns:
        Количество рабочих дней (int)
    """
    if not start_date or not end_date:
        return 0
    
    # Конвертировать datetime в date если нужно
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday
        if current_date.weekday() < 5:  # 0-4 это пн-пт
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def calculate_work_capacity(business_days):
    """
    Рассчитывает рабочую емкость одного человека в часах
    
    Args:
        business_days: Количество рабочих дней
        
    Returns:
        Рабочая емкость в часах (float)
    """
    return business_days * 8


def calculate_available_work_hours(date_start, date_end, default_hours=160):
    """
    Рассчитывает доступные рабочие часы для периода
    
    Использует модель MS Project:
    - 1 календарный день = 5/7 рабочих дней
    - 1 рабочий день = 8 часов
    
    Args:
        date_start: Начало периода (datetime.date, datetime или None)
        date_end: Конец периода (datetime.date, datetime или None)
        default_hours: Значение по умолчанию если даты не указаны
        
    Returns:
        Доступные рабочие часы (float)
    """
    if not date_start or not date_end:
        return default_hours
    
    # Конвертировать date в datetime для вычислений
    from datetime import datetime as dt_class
    if isinstance(date_start, datetime):
        range_start_dt = date_start
    else:
        range_start_dt = dt_class.combine(date_start, dt_class.min.time())
    
    if isinstance(date_end, datetime):
        range_end_dt = date_end
    else:
        range_end_dt = dt_class.combine(date_end, dt_class.max.time())
    
    range_duration = range_end_dt - range_start_dt
    calendar_days = range_duration.total_seconds() / (24 * 3600)
    
    if calendar_days <= 0:
        # Minimum: 1 workday = 8 hours
        return 8
    else:
        # Count workdays (approximate: 5/7 of calendar days are workdays)
        workdays = calendar_days * (5.0 / 7.0)
        # 8 hours per workday
        return workdays * 8


# ============================================================================
# Поиск задач по комбинации ключей
# ============================================================================

def find_task_by_name_and_dates(tasks, task_name, task_start=None, task_finish=None):
    """
    Находит задачу по комбинации имени и дат
    
    Args:
        tasks: Список словарей с задачами
        task_name: Имя задачи
        task_start: Дата начала задачи (строка или None)
        task_finish: Дата окончания задачи (строка или None)
        
    Returns:
        Найденная задача (словарь) или None
    """
    if not task_name:
        return None
    
    # Нормализовать даты для сравнения
    normalized_start = None
    normalized_finish = None
    
    if task_start:
        if isinstance(task_start, str):
            parsed_start = parse_date(task_start)
            normalized_start = parsed_start.date() if parsed_start else None
        else:
            normalized_start = task_start
    
    if task_finish:
        if isinstance(task_finish, str):
            parsed_finish = parse_date(task_finish)
            normalized_finish = parsed_finish.date() if parsed_finish else None
        else:
            normalized_finish = task_finish
    
    # Поиск задачи
    for task in tasks:
        task_name_match = task.get('name', '') == task_name
        
        if not task_name_match:
            continue
        
        # Если даты не указаны, вернуть первую найденную задачу с таким именем
        if not normalized_start and not normalized_finish:
            return task
        
        # Сравнить даты начала
        task_start_str = task.get('start', '')
        task_start_parsed = None
        if task_start_str:
            parsed = parse_date(task_start_str)
            task_start_parsed = parsed.date() if parsed else None
        
        # Сравнить даты окончания
        task_finish_str = task.get('finish', '')
        task_finish_parsed = None
        if task_finish_str:
            parsed = parse_date(task_finish_str)
            task_finish_parsed = parsed.date() if parsed else None
        
        # Проверка соответствия дат
        start_match = True
        finish_match = True
        
        if normalized_start:
            start_match = (task_start_parsed == normalized_start)
        
        if normalized_finish:
            finish_match = (task_finish_parsed == normalized_finish)
        
        if start_match and finish_match:
            return task
    
    return None

