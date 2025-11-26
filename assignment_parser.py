"""
Модуль для парсинга назначений (assignments) из XML файлов MS Project
"""
from msproject_utils import setup_logger, get_text, make_tag, find_elements

# Настройка логирования
logger = setup_logger(__name__)


def parse_assignments(root, namespace, resources, tasks):
    """
    Парсинг назначений ресурсов на задачи из XML файла MS Project
    
    Args:
        root: Корневой элемент XML дерева
        namespace: Словарь namespace или пустой словарь
        resources: Список словарей с информацией о ресурсах (должен содержать поле 'id')
        tasks: Список словарей с информацией о задачах (должен содержать поле 'id')
    
    Returns:
        Список словарей с информацией о назначениях:
        [{
            'task_id': task_uid,  # Сохраняется только для отладки и зависимостей
            'task_name': task_name,  # Имя задачи для связывания
            'task_start': task_start,  # Дата начала задачи для связывания
            'task_finish': task_finish,  # Дата окончания задачи для связывания
            'resource_name': resource_name,  # Имя ресурса (парсим только по имени)
            'work': work,
            'units': units
        }, ...]
    """
    assignments = []
    
    # Поиск всех элементов Assignment
    assignment_elements = find_elements(root, 'Assignment', namespace)
    
    logger.info(f"Найдено {len(assignment_elements)} элементов Assignment в XML")
    
    # Создать множества для быстрой проверки существования
    resource_ids = {str(r['id']) for r in resources}  # Преобразуем в строки для сравнения
    task_ids = {str(t['id']) for t in tasks}  # Преобразуем в строки для сравнения
    
    logger.debug(f"Доступные resource_ids: {sorted(resource_ids)[:10]}... (всего {len(resource_ids)})")
    logger.debug(f"Доступные task_ids: {sorted(task_ids)[:10]}... (всего {len(task_ids)})")
    
    skipped_no_resource = 0
    skipped_no_task = 0
    skipped_no_uid = 0
    parsed_count = 0
    
    for idx, assignment in enumerate(assignment_elements):
        try:
            task_uid = get_text(assignment, make_tag('TaskUID', namespace), namespace)
            resource_uid = get_text(assignment, make_tag('ResourceUID', namespace), namespace)
            work = get_text(assignment, make_tag('Work', namespace), namespace)
            
            # Попытка извлечь имя ресурса напрямую из XML
            resource_name_direct = get_text(assignment, make_tag('ResourceName', namespace), namespace, default='')
            
            # Валидация: проверяем существование ресурса и задачи
            if not task_uid or not resource_uid:
                if not task_uid and not resource_uid:
                    logger.warning(f"Назначение #{idx}: пропущено из-за пустых TaskUID и ResourceUID")
                elif not task_uid:
                    logger.warning(f"Назначение #{idx}: пропущено из-за пустого TaskUID (ResourceUID={resource_uid})")
                else:
                    logger.warning(f"Назначение #{idx}: пропущено из-за пустого ResourceUID (TaskUID={task_uid})")
                skipped_no_uid += 1
                continue
            
            # Преобразуем в строки для сравнения
            resource_uid_str = str(resource_uid)
            task_uid_str = str(task_uid)
            
            # Получить имя ресурса
            resource_name = None
            if resource_name_direct:
                # Использовать имя из XML напрямую
                resource_name = resource_name_direct
                logger.debug(f"Назначение #{idx}: resource_name извлечен напрямую из XML: {resource_name}")
            else:
                # Использовать текущую логику (поиск по ResourceUID)
                # Проверка существования ресурса по ID (для парсинга XML)
                if resource_uid_str not in resource_ids:
                    skipped_no_resource += 1
                    continue
                
                # Найти ресурс по ID для получения имени
                resource = next((r for r in resources if str(r['id']) == resource_uid_str), None)
                if not resource:
                    logger.warning(f"Назначение #{idx}: Ресурс с ID={resource_uid_str} не найден!")
                    skipped_no_resource += 1
                    continue
                
                # Получить имя ресурса
                resource_name = resource.get('name', '')
                if not resource_name:
                    logger.warning(f"Назначение #{idx}: Ресурс с ID={resource_uid_str} не имеет имени!")
                    skipped_no_resource += 1
                    continue
                logger.debug(f"Назначение #{idx}: resource_name получен через ResourceUID: {resource_name}")
            
            # Проверка существования задачи
            if task_uid_str not in task_ids:
                if task_uid_str == '1477' or (idx < 5):
                    logger.warning(f"Назначение #{idx}: TaskUID={task_uid} НЕ НАЙДЕН в списке задач!")
                skipped_no_task += 1
                continue
            
            # Найти задачу по UID для получения имени и дат
            task = next((t for t in tasks if str(t['id']) == task_uid_str), None)
            if not task:
                logger.warning(f"Назначение #{idx}: Задача с ID={task_uid_str} не найдена!")
                skipped_no_task += 1
                continue
            
            # Извлечь имя задачи и даты
            task_name = task.get('name', '')
            task_start = task.get('start', '')
            task_finish = task.get('finish', '')
            
            if not task_name:
                logger.warning(f"Назначение #{idx}: Задача с ID={task_uid_str} не имеет имени!")
                skipped_no_task += 1
                continue
            
            # Добавление назначения с именами и датами для связывания
            assignments.append({
                'task_id': task_uid_str,  # Сохраняем для отладки и зависимостей
                'task_name': task_name,  # Для связывания
                'task_start': task_start,  # Для связывания
                'task_finish': task_finish,  # Для связывания
                'resource_name': resource_name,  # Для связывания
                'work': work,
                'units': get_text(assignment, make_tag('Units', namespace), namespace, default='1.0')
            })
            parsed_count += 1
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге назначения #{idx}: {e}", exc_info=True)
            continue
    
    logger.info(f"Парсинг назначений завершен:")
    logger.info(f"  Найдено: {len(assignment_elements)}")
    logger.info(f"  Обработано: {parsed_count}")
    logger.info(f"  Пропущено (нет ресурса): {skipped_no_resource}")
    logger.info(f"  Пропущено (нет задачи): {skipped_no_task}")
    logger.info(f"  Пропущено (нет UID): {skipped_no_uid}")
    
    # Проверка корректности: убедиться, что для каждого назначения есть соответствующий ресурс и задача
    logger.info("=== ПРОВЕРКА КОРРЕКТНОСТИ СВЯЗЫВАНИЯ РЕСУРСОВ С ЗАДАЧАМИ ===")
    incorrect_assignments = 0
    for assignment in assignments:
        resource_name = assignment.get('resource_name')
        task_name = assignment.get('task_name')
        task_start = assignment.get('task_start')
        task_finish = assignment.get('task_finish')
        task_id = assignment.get('task_id', 'N/A')  # Только для отладки
        
        # Проверка наличия имени ресурса
        if not resource_name:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Назначение не содержит resource_name для TaskName={task_name} (TaskID={task_id})!")
            incorrect_assignments += 1
            continue
        
        # Найти ресурс по имени
        resource = next((r for r in resources if r.get('name') == resource_name), None)
        if not resource:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Ресурс с именем '{resource_name}' не найден для назначения TaskName={task_name} (TaskID={task_id})!")
            incorrect_assignments += 1
            continue
        
        # Найти задачу по комбинации имени и дат
        task = None
        for t in tasks:
            if t.get('name') == task_name:
                # Проверить соответствие дат
                start_match = (not task_start) or (t.get('start') == task_start)
                finish_match = (not task_finish) or (t.get('finish') == task_finish)
                if start_match and finish_match:
                    task = t
                    break
        
        if not task:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Задача с именем '{task_name}' (Start={task_start}, Finish={task_finish}) не найдена для назначения ресурса '{resource_name}' (TaskID={task_id})!")
            incorrect_assignments += 1
            continue
    
    if incorrect_assignments == 0:
        logger.info(f"✓ Все назначения корректно связаны с ресурсами и задачами")
    else:
        logger.warning(f"✗ Найдено {incorrect_assignments} некорректных назначений!")
    
    return assignments

