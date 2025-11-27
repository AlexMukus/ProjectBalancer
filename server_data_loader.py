"""
Модуль для загрузки данных из MS Project Server через REST API
Использует активное подключение для получения проектов и ресурсов

ВАЖНО: ВСЕ ОПЕРАЦИИ С СЕРВЕРОМ СТРОГО ТОЛЬКО ДЛЯ ЧТЕНИЯ!
Изменение данных на сервере строго запрещено.
Допускается только чтение данных через GET запросы.
"""
import requests
import json
import re
from urllib.parse import urlparse, urlunparse, parse_qs
from html import unescape
from msproject_utils import setup_logger

# Настройка логирования
logger = setup_logger(__name__)

# Константа для обеспечения read-only режима
READ_ONLY_MODE = True  # Строго только чтение, изменения запрещены


class MSProjectServerDataLoader:
    """
    Класс для загрузки данных из MS Project Server
    
    Использует активное подключение для получения списков проектов и ресурсов
    через REST API с логированием всех операций.
    
    ВАЖНО: Класс работает строго в режиме ТОЛЬКО ДЛЯ ЧТЕНИЯ.
    Все операции выполняются исключительно через GET запросы.
    Изменение данных на сервере строго запрещено.
    """
    
    def __init__(self, connection):
        """
        Инициализация загрузчика данных
        
        Args:
            connection: Экземпляр MSProjectServerConnection с активным подключением
        
        ВАЖНО: Загрузчик работает только в режиме чтения.
        """
        self._connection = connection
        if not READ_ONLY_MODE:
            logger.warning("ВНИМАНИЕ: READ_ONLY_MODE отключен! Это недопустимо.")
    
    def _get_json_headers(self):
        """
        Возвращает заголовки для запроса JSON данных
        
        Returns:
            dict: Словарь с заголовками для JSON запросов
        """
        return {
            'Accept': 'application/json, text/json, */*',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
    
    def _parse_html_tags_projects(self, html_text):
        """
        Парсит проекты из HTML-тегов <a> с атрибутом projectaddress
        
        Args:
            html_text: HTML текст для парсинга
        
        Returns:
            list: Список словарей с информацией о проектах
        """
        projects = []
        
        # Подсчет всех тегов <a> с атрибутом projectaddress на странице
        count_pattern = r'<a[^>]*projectaddress[^>]*>'
        all_matches = re.findall(count_pattern, html_text, re.IGNORECASE)
        logger.info(f"Общее число тегов <a> с атрибутом projectaddress на странице: {len(all_matches)}")
        
        # Более гибкий паттерн для поиска тегов <a> с атрибутом projectaddress
        # Учитывает произвольное количество пробелов, порядок атрибутов и вложенные теги
        pattern = r'<a[^>]*\s+projectaddress\s*=\s*"([^"]+)"[^>]*>(.*?)</a>'
        
        matches = re.findall(pattern, html_text, re.DOTALL | re.IGNORECASE)
        
        logger.info(f"Найдено совпадений тегов проектов: {len(matches)}")
        
        for url, name_html in matches:
            try:
                # Декодируем HTML entities в URL
                url_decoded = unescape(url)
                
                # Удаляем все HTML-теги из текста и очищаем от лишних пробелов
                name_clean = re.sub(r'<[^>]+>', '', name_html).strip()
                # Удаляем лишние пробелы и переносы строк
                name_clean = ' '.join(name_clean.split())
                
                # Парсим URL для извлечения ProjUid
                parsed_url = urlparse(url_decoded)
                query_params = parse_qs(parsed_url.query)
                
                proj_uid = None
                if 'ProjUid' in query_params:
                    proj_uid = query_params['ProjUid'][0] if query_params['ProjUid'] else None
                
                project = {
                    'Name': name_clean,
                    'ProjectAddress': url_decoded,
                    'Url': url_decoded,
                }
                
                if proj_uid:
                    project['Id'] = proj_uid
                    project['ProjUid'] = proj_uid
                
                projects.append(project)
                
            except Exception as e:
                logger.warning(f"Ошибка при парсинге проекта: {str(e)}")
                continue
        
        logger.info(f"Успешно извлечено проектов из HTML-тегов: {len(projects)}")
        if projects:
            logger.info(f"Примеры проектов (первые {min(2, len(projects))}):")
            for i, project in enumerate(projects[:2]):
                logger.info(f"  Проект #{i+1}: Name='{project.get('Name')}', Id='{project.get('Id', 'N/A')}'")
        
        return projects
    
    def _parse_html_tags_resources(self, html_text):
        """
        Парсит ресурсы из HTML-таблицы с ячейками <td role="gridcell"> содержащими <span>
        
        Args:
            html_text: HTML текст для парсинга
        
        Returns:
            list: Список словарей с информацией о ресурсах
        """
        resources = []
        # Паттерн для поиска ячеек с title атрибутом
        pattern_with_title = r'<td[^>]*role="gridcell"[^>]*>.*?<span[^>]*title="([^"]*)"[^>]*class="jsgrid-control-text"[^>]*>([^<]*)</span>.*?</td>'
        # Альтернативный паттерн без title
        pattern_without_title = r'<td[^>]*role="gridcell"[^>]*>.*?<span[^>]*class="jsgrid-control-text"[^>]*>([^<]*)</span>.*?</td>'
        
        # Сначала пробуем с title
        matches = re.findall(pattern_with_title, html_text, re.DOTALL | re.IGNORECASE)
        
        if not matches:
            # Если не нашли с title, пробуем без title
            matches = re.findall(pattern_without_title, html_text, re.DOTALL | re.IGNORECASE)
            logger.info(f"Найдено совпадений тегов ресурсов (без title): {len(matches)}")
        else:
            logger.info(f"Найдено совпадений тегов ресурсов (с title): {len(matches)}")
        
        for match in matches:
            try:
                # Если match - кортеж (с title), берем title или текст
                if isinstance(match, tuple):
                    if len(match) == 2:
                        # Есть title
                        name = match[0].strip() if match[0].strip() else match[1].strip()
                    else:
                        # Только текст
                        name = match[0].strip()
                else:
                    # match - строка
                    name = match.strip()
                
                if not name:
                    continue
                
                resource = {
                    'Name': name,
                    'ResourceName': name,  # Дублирование для совместимости
                }
                
                resources.append(resource)
                
            except Exception as e:
                logger.warning(f"Ошибка при парсинге ресурса: {str(e)}")
                continue
        
        logger.info(f"Успешно извлечено ресурсов из HTML-тегов: {len(resources)}")
        if resources:
            logger.info(f"Примеры ресурсов (первые {min(2, len(resources))}):")
            for i, resource in enumerate(resources[:2]):
                logger.info(f"  Ресурс #{i+1}: Name='{resource.get('Name')}'")
        
        return resources
    
    def _parse_response(self, response, entity_type=None):
        """
        Парсит ответ сервера, пытаясь определить формат (JSON, HTML, XML)
        
        Args:
            response: requests.Response объект
            entity_type: Тип сущности ('Projects' или 'Resources') для парсинга HTML-тегов
        
        Returns:
            tuple: (data, format_type) где data - распарсенные данные, 
                   format_type - 'json', 'html', 'xml', 'html_tags' или None
        """
        content_type = response.headers.get('Content-Type', '').lower()
        text = response.text
        
        # Проверяем Content-Type
        if 'application/json' in content_type or 'text/json' in content_type:
            try:
                data = response.json()
                return data, 'json'
            except ValueError:
                logger.warning("Content-Type указывает JSON, но парсинг не удался")
        
        # Пытаемся распарсить как JSON
        try:
            data = response.json()
            return data, 'json'
        except ValueError:
            pass
        
        # Проверяем, не является ли это HTML
        if content_type.startswith('text/html') or text.strip().startswith('<!DOCTYPE') or text.strip().startswith('<html'):
            logger.info("Сервер вернул HTML. Парсим HTML-теги.")
            # Сразу парсим HTML-теги без поиска JSON
            if entity_type:
                if entity_type == 'Projects':
                    projects = self._parse_html_tags_projects(text)
                    if projects:
                        logger.info(f"✓ Успешно извлечено проектов из HTML-тегов: {len(projects)}")
                        return projects, 'html_tags'
                elif entity_type == 'Resources':
                    resources = self._parse_html_tags_resources(text)
                    if resources:
                        logger.info(f"✓ Успешно извлечено ресурсов из HTML-тегов: {len(resources)}")
                        return resources, 'html_tags'
            else:
                # Если entity_type не указан, пробуем оба варианта
                projects = self._parse_html_tags_projects(text)
                if projects:
                    logger.info(f"✓ Успешно извлечено проектов из HTML-тегов: {len(projects)}")
                    return projects, 'html_tags'
                
                resources = self._parse_html_tags_resources(text)
                if resources:
                    logger.info(f"✓ Успешно извлечено ресурсов из HTML-тегов: {len(resources)}")
                    return resources, 'html_tags'
            
            # Если не нашли данные в HTML-тегах, возвращаем HTML как есть
            return text, 'html'
        
        # Проверяем XML
        if content_type.startswith('application/xml') or content_type.startswith('text/xml') or text.strip().startswith('<?xml'):
            return text, 'xml'
        
        # Неизвестный формат
        logger.warning(f"Неизвестный формат ответа. Content-Type: {content_type}")
        return text, None
    
    def _load_data_from_endpoint(self, session, base_url, entity_name):
        """
        Загружает данные из эндпоинта, парся HTML-теги
        
        Args:
            session: requests.Session с активной аутентификацией
            base_url: Базовый URL сервера (схема + хост)
            entity_name: Имя сущности ('Projects' или 'Resources')
        
        Returns:
            tuple: (data, endpoint_url) или (None, None) если не удалось загрузить
        """
        # Используем только один вариант эндпоинта
        endpoint_url = f"{base_url}/{entity_name}.aspx"
        
        headers = self._get_json_headers()
        
        try:
            logger.info(f"Запрос к эндпоинту: {endpoint_url}")
            
            # ВАЖНО: Используется ТОЛЬКО GET запрос для чтения данных
            response = session.get(endpoint_url, headers=headers, timeout=30)
            
            logger.info(f"Статус ответа: {response.status_code}")
            logger.info(f"Content-Type: {response.headers.get('Content-Type', 'не указан')}")
            
            # Проверка статуса ответа
            if response.status_code == 200:
                # Парсинг ответа
                logger.info("Парсинг ответа сервера...")
                data, format_type = self._parse_response(response, entity_type=entity_name)
                
                # Проверяем формат html_tags
                if format_type == 'html_tags':
                    logger.info(f"✓ Успешно получены данные в формате html_tags из: {endpoint_url}")
                    
                    # Детальное логирование структуры полученных данных
                    logger.info("=== Информация о полученных данных ===")
                    logger.info(f"Тип данных: {type(data).__name__}")
                    
                    if isinstance(data, dict):
                        logger.info(f"Структура данных (dict): ключи = {list(data.keys())}, количество ключей = {len(data)}")
                        # Логируем первые 500 символов структуры
                        logger.info(f"Структура данных (первые 500 символов): {str(data)[:500]}")
                    elif isinstance(data, list):
                        logger.info(f"Структура данных (list): длина списка = {len(data)}")
                        if len(data) > 0:
                            logger.info(f"Тип элементов списка: {type(data[0]).__name__}")
                            # Логируем первые 1-2 записи для диагностики
                            for i, item in enumerate(data[:2]):
                                if isinstance(item, dict):
                                    logger.info(f"Запись #{i+1}: ключи = {list(item.keys())}")
                                    logger.info(f"Запись #{i+1} (первые 200 символов): {str(item)[:200]}")
                                else:
                                    logger.info(f"Запись #{i+1}: {str(item)[:200]}")
                    else:
                        logger.info(f"Структура данных: тип = {type(data).__name__}")
                        logger.info(f"Данные (первые 500 символов): {str(data)[:500]}")
                    
                    logger.info("=== Конец информации о данных ===")
                    return data, endpoint_url
                else:
                    logger.error(f"Ожидался формат html_tags, но получен формат: {format_type}")
                    if format_type == 'html':
                        logger.debug(f"Первые 500 символов HTML: {response.text[:500]}")
                    return None, None
            
            elif response.status_code == 401:
                logger.error(f"Ошибка аутентификации для {endpoint_url}")
                return None, None
            elif response.status_code == 404:
                logger.error(f"Эндпоинт не найден (404) для {endpoint_url}")
                return None, None
            else:
                logger.error(f"Ошибка при запросе. Статус: {response.status_code} для {endpoint_url}")
                return None, None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса для {endpoint_url}: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Неожиданная ошибка для {endpoint_url}: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return None, None
    
    def load_projects(self):
        """
        Загружает список проектов из MS Project Server
        
        ВАЖНО: Операция ТОЛЬКО ДЛЯ ЧТЕНИЯ. Используется только GET запрос.
        Изменение данных на сервере строго запрещено.
        
        Returns:
            list: Список словарей с информацией о проектах:
            [{'Name': '...', 'Id': '...'}, ...]
            Пустой список при ошибке
        """
        if not self._connection.is_connected():
            logger.error("Попытка загрузки проектов при отсутствии активного подключения")
            return []
        
        session = self._connection.get_session()
        server_url = self._connection.get_server_url()
        
        if not session or not server_url:
            logger.error("Не удалось получить сессию или URL сервера")
            return []
        
        try:
            # Извлекаем базовый URL
            parsed = urlparse(server_url)
            base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
            
            logger.info(f"Загрузка проектов (READ-ONLY режим)")
            
            # Загрузка данных из эндпоинта
            data, successful_url = self._load_data_from_endpoint(session, base_url, "Projects")
            
            if data is None:
                logger.error("Не удалось загрузить данные проектов")
                return []
            
            logger.info("=== Извлечение данных проектов из структуры ===")
            
            # Парсинг OData формата с рекурсивным поиском
            projects = []
            
            def find_list_in_dict(obj, path=""):
                """Рекурсивно ищет списки в словаре"""
                if isinstance(obj, list):
                    if len(obj) > 0 and isinstance(obj[0], dict):
                        return obj
                    return None
                elif isinstance(obj, dict):
                    # Проверяем стандартные ключи OData
                    if 'results' in obj:
                        if isinstance(obj['results'], list):
                            return obj['results']
                    if 'value' in obj:
                        if isinstance(obj['value'], list):
                            return obj['value']
                    
                    # Рекурсивно ищем в значениях
                    for key, value in obj.items():
                        result = find_list_in_dict(value, f"{path}.{key}" if path else key)
                        if result:
                            logger.debug(f"Найдены данные по пути: {path}.{key}" if path else f"Найдены данные в ключе: {key}")
                            return result
                return None
            
            if isinstance(data, dict):
                # Стандартные форматы OData
                if 'd' in data:
                    if isinstance(data['d'], dict) and 'results' in data['d']:
                        projects = data['d']['results']
                    elif isinstance(data['d'], list):
                        projects = data['d']
                    elif isinstance(data['d'], dict):
                        # Рекурсивный поиск в data['d']
                        projects = find_list_in_dict(data['d']) or []
                elif 'value' in data:
                    projects = data['value'] if isinstance(data['value'], list) else []
                else:
                    # Рекурсивный поиск во всей структуре
                    projects = find_list_in_dict(data) or []
                    if not projects:
                        # Пытаемся найти данные в других ключах (не рекурсивно)
                        logger.debug(f"Структура JSON: {list(data.keys())}")
                        for key, value in data.items():
                            if isinstance(value, list):
                                projects = value
                                logger.debug(f"Найдены данные в ключе: {key}")
                                break
            elif isinstance(data, list):
                projects = data
            else:
                logger.warning(f"Неожиданный формат данных. Тип: {type(data)}")
                logger.debug(f"Структура данных: {str(data)[:200]}")
                return []
            
            # Обработка результатов с детальным логированием
            logger.info("=== Информация о считанных проектах ===")
            if projects:
                logger.info(f"✓ Успешно извлечено проектов: {len(projects)}")
                logger.info(f"Источник данных: {successful_url}")
                
                # Логируем примеры записей
                if len(projects) > 0:
                    logger.info(f"Примеры записей (первые {min(2, len(projects))}):")
                    for i, project in enumerate(projects[:2]):
                        if isinstance(project, dict):
                            logger.info(f"  Проект #{i+1}:")
                            logger.info(f"    Ключи: {list(project.keys())}")
                            # Логируем основные поля если они есть
                            for key in ['Name', 'ProjectName', 'Id', 'ProjectId', 'Title']:
                                if key in project:
                                    logger.info(f"    {key}: {project[key]}")
                            logger.info(f"    Полная запись (первые 300 символов): {str(project)[:300]}")
                        else:
                            logger.info(f"  Проект #{i+1}: {str(project)[:200]}")
                
                logger.info(f"Общая статистика: найдено {len(projects)} проектов")
                logger.info("=== Конец информации о проектах ===")
                return projects
            else:
                # Данные получены, но список пуст - это валидная ситуация (просто нет записей)
                logger.info(f"Данные получены из {successful_url}, но список проектов пуст (0 записей)")
                logger.info(f"Структура исходных данных: {str(data)[:500]}")
                logger.info("=== Конец информации о проектах ===")
                return []  # Возвращаем пустой список, не ошибку
                
        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при загрузке проектов")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка соединения при загрузке проектов: {str(e)}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса при загрузке проектов: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке проектов: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def load_resources(self):
        """
        Загружает список ресурсов из MS Project Server
        
        ВАЖНО: Операция ТОЛЬКО ДЛЯ ЧТЕНИЯ. Используется только GET запрос.
        Изменение данных на сервере строго запрещено.
        
        Returns:
            list: Список словарей с информацией о ресурсах:
            [{'Name': '...', 'Id': '...'}, ...]
            Пустой список при ошибке
        """
        if not self._connection.is_connected():
            logger.error("Попытка загрузки ресурсов при отсутствии активного подключения")
            return []
        
        session = self._connection.get_session()
        server_url = self._connection.get_server_url()
        
        if not session or not server_url:
            logger.error("Не удалось получить сессию или URL сервера")
            return []
        
        try:
            # Извлекаем базовый URL
            parsed = urlparse(server_url)
            base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
            
            logger.info(f"Загрузка ресурсов (READ-ONLY режим)")
            
            # Загрузка данных из эндпоинта
            data, successful_url = self._load_data_from_endpoint(session, base_url, "Resources")
            
            if data is None:
                logger.error("Не удалось загрузить данные ресурсов")
                return []
            
            logger.info("=== Извлечение данных ресурсов из структуры ===")
            
            # Парсинг OData формата с рекурсивным поиском
            resources = []
            
            def find_list_in_dict(obj, path=""):
                """Рекурсивно ищет списки в словаре"""
                if isinstance(obj, list):
                    if len(obj) > 0 and isinstance(obj[0], dict):
                        return obj
                    return None
                elif isinstance(obj, dict):
                    # Проверяем стандартные ключи OData
                    if 'results' in obj:
                        if isinstance(obj['results'], list):
                            return obj['results']
                    if 'value' in obj:
                        if isinstance(obj['value'], list):
                            return obj['value']
                    
                    # Рекурсивно ищем в значениях
                    for key, value in obj.items():
                        result = find_list_in_dict(value, f"{path}.{key}" if path else key)
                        if result:
                            logger.debug(f"Найдены данные по пути: {path}.{key}" if path else f"Найдены данные в ключе: {key}")
                            return result
                return None
            
            if isinstance(data, dict):
                # Стандартные форматы OData
                if 'd' in data:
                    if isinstance(data['d'], dict) and 'results' in data['d']:
                        resources = data['d']['results']
                    elif isinstance(data['d'], list):
                        resources = data['d']
                    elif isinstance(data['d'], dict):
                        # Рекурсивный поиск в data['d']
                        resources = find_list_in_dict(data['d']) or []
                elif 'value' in data:
                    resources = data['value'] if isinstance(data['value'], list) else []
                else:
                    # Рекурсивный поиск во всей структуре
                    resources = find_list_in_dict(data) or []
                    if not resources:
                        # Пытаемся найти данные в других ключах (не рекурсивно)
                        logger.debug(f"Структура JSON: {list(data.keys())}")
                        for key, value in data.items():
                            if isinstance(value, list):
                                resources = value
                                logger.debug(f"Найдены данные в ключе: {key}")
                                break
            elif isinstance(data, list):
                resources = data
            else:
                logger.warning(f"Неожиданный формат данных. Тип: {type(data)}")
                logger.debug(f"Структура данных: {str(data)[:200]}")
                return []
            
            # Обработка результатов с детальным логированием
            logger.info("=== Информация о считанных ресурсах ===")
            if resources:
                logger.info(f"✓ Успешно извлечено ресурсов: {len(resources)}")
                logger.info(f"Источник данных: {successful_url}")
                
                # Логируем примеры записей
                if len(resources) > 0:
                    logger.info(f"Примеры записей (первые {min(2, len(resources))}):")
                    for i, resource in enumerate(resources[:2]):
                        if isinstance(resource, dict):
                            logger.info(f"  Ресурс #{i+1}:")
                            logger.info(f"    Ключи: {list(resource.keys())}")
                            # Логируем основные поля если они есть
                            for key in ['Name', 'ResourceName', 'Id', 'ResourceId', 'Title']:
                                if key in resource:
                                    logger.info(f"    {key}: {resource[key]}")
                            logger.info(f"    Полная запись (первые 300 символов): {str(resource)[:300]}")
                        else:
                            logger.info(f"  Ресурс #{i+1}: {str(resource)[:200]}")
                
                logger.info(f"Общая статистика: найдено {len(resources)} ресурсов")
                logger.info("=== Конец информации о ресурсах ===")
                return resources
            else:
                # Данные получены, но список пуст - это валидная ситуация (просто нет записей)
                logger.info(f"Данные получены из {successful_url}, но список ресурсов пуст (0 записей)")
                logger.info(f"Структура исходных данных: {str(data)[:500]}")
                logger.info("=== Конец информации о ресурсах ===")
                return []  # Возвращаем пустой список, не ошибку
                
        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при загрузке ресурсов")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка соединения при загрузке ресурсов: {str(e)}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса при загрузке ресурсов: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке ресурсов: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

