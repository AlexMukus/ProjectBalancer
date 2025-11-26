"""
Тестовый скрипт для проверки парсинга ресурсов из XML файла MS Project
"""
import logging
from lxml import etree
import io
from resource_parser import parse_resources, get_text

# Настройка логирования для тестирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_parse_resources(xml_file_path):
    """
    Тестирует парсинг ресурсов из XML файла
    
    Args:
        xml_file_path: Путь к XML файлу MS Project
    """
    try:
        logger.info(f"Начинаем тестирование парсинга ресурсов из файла: {xml_file_path}")
        
        # Читаем XML файл
        with open(xml_file_path, 'rb') as f:
            xml_content = f.read()
        
        # Парсим XML
        tree = etree.parse(io.BytesIO(xml_content))
        root = tree.getroot()
        
        # Получаем namespace
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        logger.info(f"Namespace: {namespace}")
        
        # Парсим ресурсы
        resources = parse_resources(root, namespace, filter_inactive=True)
        
        # Выводим результаты
        logger.info(f"\n{'='*60}")
        logger.info(f"РЕЗУЛЬТАТЫ ПАРСИНГА РЕСУРСОВ")
        logger.info(f"{'='*60}")
        logger.info(f"Всего найдено ресурсов: {len(resources)}")
        
        # Ищем ресурс "Иванов Илья Евгеньевич"
        ivanov_found = False
        ivanov_resource = None
        
        for resource in resources:
            if 'Иванов' in resource['name'] or resource['id'] == '44':
                ivanov_found = True
                ivanov_resource = resource
                logger.info(f"\n{'='*60}")
                logger.info(f"НАЙДЕН РЕСУРС ИВАНОВ ИЛЬЯ ЕВГЕНЬЕВИЧ:")
                logger.info(f"  UID: {resource['id']}")
                logger.info(f"  Name: {resource['name']}")
                logger.info(f"  MaxUnits: {resource['max_units']}")
                logger.info(f"  IsInactive: {resource.get('is_inactive', 'N/A')}")
                logger.info(f"{'='*60}")
                break
        
        if not ivanov_found:
            logger.warning(f"\n{'='*60}")
            logger.warning(f"РЕСУРС 'ИВАНОВ ИЛЬЯ ЕВГЕНЬЕВИЧ' НЕ НАЙДЕН!")
            logger.warning(f"{'='*60}")
        
        # Выводим первые 10 ресурсов для проверки
        logger.info(f"\n{'='*60}")
        logger.info(f"ПЕРВЫЕ 10 РЕСУРСОВ:")
        logger.info(f"{'='*60}")
        for i, resource in enumerate(resources[:10], 1):
            logger.info(f"{i}. UID={resource['id']}, Name={resource['name']}, MaxUnits={resource['max_units']}")
        
        # Проверяем, есть ли ресурсы с UID=44
        resources_with_uid_44 = [r for r in resources if r['id'] == '44']
        if resources_with_uid_44:
            logger.info(f"\n{'='*60}")
            logger.info(f"РЕСУРСЫ С UID=44:")
            logger.info(f"{'='*60}")
            for resource in resources_with_uid_44:
                logger.info(f"  UID={resource['id']}, Name={resource['name']}, MaxUnits={resource['max_units']}")
        else:
            logger.warning(f"\n{'='*60}")
            logger.warning(f"РЕСУРСЫ С UID=44 НЕ НАЙДЕНЫ!")
            logger.warning(f"{'='*60}")
        
        return resources, ivanov_resource
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании парсинга ресурсов: {e}", exc_info=True)
        return None, None


if __name__ == '__main__':
    # Тестируем на реальном XML файле
    xml_file = r"АПМЦ.25-01.00.00.000 Станции гидравлические для испытаний и промывки гидроцилиндров АМГ-10 и Skydrol LD-4.xml"
    
    try:
        resources, ivanov = test_parse_resources(xml_file)
        
        if resources:
            print(f"\n✓ Тест завершен успешно. Найдено {len(resources)} ресурсов.")
            if ivanov:
                print(f"✓ Ресурс 'Иванов Илья Евгеньевич' найден: UID={ivanov['id']}, Name={ivanov['name']}")
            else:
                print(f"✗ Ресурс 'Иванов Илья Евгеньевич' не найден!")
        else:
            print(f"\n✗ Тест завершен с ошибкой.")
            
    except FileNotFoundError:
        print(f"\n✗ Файл не найден: {xml_file}")
        print("Убедитесь, что файл находится в текущей директории.")
    except Exception as e:
        print(f"\n✗ Ошибка при выполнении теста: {e}")

