"""
Модуль для парсинга ресурсов из XML файлов MS Project
"""
from msproject_utils import setup_logger, get_text, make_tag, find_elements

# Настройка логирования
logger = setup_logger(__name__)


def parse_resources(root, namespace, filter_inactive=True):
    """
    Парсинг информации о ресурсах из XML файла MS Project
    
    Args:
        root: Корневой элемент XML дерева
        namespace: Словарь namespace или пустой словарь
        filter_inactive: Если True, пропускать ресурсы с IsInactive=1
    
    Returns:
        Список словарей с информацией о ресурсах:
        [{
            'id': resource_id,
            'name': resource_name,
            'max_units': max_units,
            'is_inactive': is_inactive
        }, ...]
    """
    resources = []
    
    # Поиск всех элементов Resource
    resource_elements = find_elements(root, 'Resource', namespace)
    
    logger.info(f"Найдено {len(resource_elements)} элементов Resource в XML")
    
    skipped_count = 0
    parsed_count = 0
    
    for idx, resource in enumerate(resource_elements):
        try:
            # Извлечение основных полей
            resource_id = get_text(resource, make_tag('UID', namespace), namespace)
            name = get_text(resource, make_tag('Name', namespace), namespace)
            
            # Проверка на пустые значения (после strip)
            # Пустая строка после strip() должна быть отфильтрована
            if not resource_id or not resource_id.strip():
                logger.warning(f"Ресурс #{idx}: пропущен из-за пустого UID")
                skipped_count += 1
                continue
            
            if not name or not name.strip():
                logger.warning(f"Ресурс #{idx} (UID={resource_id}): пропущен из-за пустого Name")
                skipped_count += 1
                continue
            
            # Извлечение MaxUnits и IsInactive
            # MaxUnits может отсутствовать - используется default значение '1.0'
            max_units = get_text(resource, make_tag('MaxUnits', namespace), namespace, default='1.0')
            is_inactive = get_text(resource, make_tag('IsInactive', namespace), namespace, default='0')
            
            # Фильтрация по IsInactive
            if filter_inactive and is_inactive == '1':
                logger.debug(f"Ресурс #{idx} (UID={resource_id}, Name={name}): пропущен из-за IsInactive=1")
                skipped_count += 1
                continue
            
            # Добавление ресурса
            # Преобразуем ID в строку для единообразия
            resources.append({
                'id': str(resource_id),
                'name': name,
                'max_units': max_units,
                'is_inactive': is_inactive
            })
            parsed_count += 1
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге ресурса #{idx}: {e}")
            skipped_count += 1
            continue
    
    logger.info(f"Парсинг ресурсов завершен: найдено {len(resource_elements)}, обработано {parsed_count}, пропущено {skipped_count}")
    
    return resources

