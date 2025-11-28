"""
Модуль для загрузки данных из MS Project Server через REST API
Использует активное подключение для получения проектов и ресурсов

ВАЖНО: ВСЕ ОПЕРАЦИИ С СЕРВЕРОМ СТРОГО ТОЛЬКО ДЛЯ ЧТЕНИЯ!
Изменение данных на сервере строго запрещено.
Допускается только чтение данных через GET запросы.
"""
import requests
import json
from urllib.parse import urlparse, urlunparse
from msproject_utils import setup_logger

# Настройка логирования
logger = setup_logger(__name__)

# Константа для обеспечения read-only режима
READ_ONLY_MODE = True  # Строго только чтение, изменения запрещены

# Константа для PWA адреса (можно изменить для разных серверов)
PWA_BASE_URL = "http://tpch-app04/_layouts/15/pwa/"


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
    
    def _load_projects_via_odata(self, session, base_url):
        """
        Загружает список проектов через OData API
        
        Пробует два варианта OData endpoints:
        1. ProjectData.svc/Projects (стандартный OData)
        2. _api/ProjectData/Projects (SharePoint REST API)
        
        Args:
            session: requests.Session с активной аутентификацией
            base_url: Базовый URL сервера (схема + хост)
        
        Returns:
            list: Список словарей с информацией о проектах или None при ошибке
        """
        headers = self._get_json_headers()
        
        # Список OData endpoints для попытки подключения
        odata_endpoints = [
            f"{base_url}/ProjectData.svc/Projects",  # Стандартный OData
            f"{base_url}/_api/ProjectData/Projects",  # SharePoint REST API
        ]
        
        for endpoint_url in odata_endpoints:
            try:
                logger.info(f"Попытка подключения к OData endpoint: {endpoint_url}")
                
                # ВАЖНО: Используется ТОЛЬКО GET запрос для чтения данных
                response = session.get(endpoint_url, headers=headers, timeout=30)
                
                logger.info(f"Статус ответа: {response.status_code}")
                logger.info(f"Content-Type: {response.headers.get('Content-Type', 'не указан')}")
                
                if response.status_code == 200:
                    try:
                        # Парсим JSON ответ
                        data = response.json()
                        logger.info(f"✓ Успешно получен JSON ответ от {endpoint_url}")
                        
                        # Извлекаем список проектов из OData формата
                        projects_list = None
                        
                        # Стандартный формат OData: {"d": {"results": [...]}}
                        if isinstance(data, dict) and 'd' in data:
                            if isinstance(data['d'], dict) and 'results' in data['d']:
                                projects_list = data['d']['results']
                                logger.info(f"Найдены проекты в формате d.results: {len(projects_list)} записей")
                            elif isinstance(data['d'], list):
                                projects_list = data['d']
                                logger.info(f"Найдены проекты в формате d (list): {len(projects_list)} записей")
                        
                        # Альтернативный формат: {"value": [...]}
                        if not projects_list and isinstance(data, dict) and 'value' in data:
                            if isinstance(data['value'], list):
                                projects_list = data['value']
                                logger.info(f"Найдены проекты в формате value: {len(projects_list)} записей")
                        
                        # Прямой список
                        if not projects_list and isinstance(data, list):
                            projects_list = data
                            logger.info(f"Найдены проекты в формате прямого списка: {len(projects_list)} записей")
                        
                        if projects_list:
                            logger.info(f"✓ Успешно загружено проектов через OData: {len(projects_list)}")
                            logger.info(f"Использован endpoint: {endpoint_url}")
                            
                            # Логируем структуру первой записи для диагностики
                            if len(projects_list) > 0 and isinstance(projects_list[0], dict):
                                logger.info(f"Пример структуры проекта (ключи): {list(projects_list[0].keys())}")
                            
                            return projects_list
                        else:
                            logger.warning(f"Получен ответ 200, но не удалось найти список проектов в структуре данных")
                            logger.debug(f"Структура данных (первые 500 символов): {str(data)[:500]}")
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка парсинга JSON от {endpoint_url}: {str(e)}")
                        logger.debug(f"Первые 500 символов ответа: {response.text[:500]}")
                        continue
                
                elif response.status_code == 401:
                    logger.warning(f"Ошибка аутентификации для {endpoint_url}")
                    continue
                elif response.status_code == 404:
                    logger.info(f"Endpoint не найден (404) для {endpoint_url}, пробуем следующий...")
                    continue
                else:
                    logger.warning(f"Неожиданный статус ответа {response.status_code} для {endpoint_url}")
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Превышено время ожидания для {endpoint_url}, пробуем следующий...")
                continue
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Ошибка соединения для {endpoint_url}: {str(e)}, пробуем следующий...")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"Ошибка запроса для {endpoint_url}: {str(e)}, пробуем следующий...")
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка для {endpoint_url}: {str(e)}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.error("Не удалось загрузить проекты ни через один OData endpoint")
        return None
    
    # Метод удален: парсинг HTML больше не используется, используется OData API
    # def _parse_html_tags_projects(self, html_text):
    #     """Удален: используется OData API вместо парсинга HTML"""
    
    # Метод упрощен: парсинг HTML больше не используется, используется OData API
    def _parse_response(self, response, entity_type=None):
        """
        Парсит ответ сервера, пытаясь определить формат (JSON, XML)
        
        Args:
            response: requests.Response объект
            entity_type: Тип сущности (не используется, оставлен для совместимости)
        
        Returns:
            tuple: (data, format_type) где data - распарсенные данные, 
                   format_type - 'json', 'xml' или None
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
        
        # Проверяем XML
        if content_type.startswith('application/xml') or content_type.startswith('text/xml') or text.strip().startswith('<?xml'):
            return text, 'xml'
        
        # Неизвестный формат
        logger.warning(f"Неизвестный формат ответа. Content-Type: {content_type}")
        return text, None
    
    # Метод удален: больше не используется, используется OData API через _load_projects_via_odata()
    # def _load_data_from_endpoint(self, session, base_url, entity_name):
    #     """Удален: используется OData API вместо парсинга HTML"""
    
    def load_projects(self):
        """
        Загружает список проектов из MS Project Server через OData API
        
        ВАЖНО: Операция ТОЛЬКО ДЛЯ ЧТЕНИЯ. Используется только GET запрос.
        Изменение данных на сервере строго запрещено.
        
        Returns:
            list: Список словарей с информацией о проектах:
            [{'Name': '...', 'Id': '...', 'ProjUid': '...', 'ProjectAddress': '...', 'Url': '...'}, ...]
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
            # Извлекаем базовый URL из server_url или используем PWA_BASE_URL
            parsed = urlparse(server_url)
            base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
            
            # Если server_url содержит путь к PWA, используем его, иначе используем константу
            if '/_layouts/15/pwa' in server_url or '/Projects.aspx' in server_url:
                # Извлекаем базовый URL из PWA пути
                base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
            else:
                # Используем базовый URL из константы PWA_BASE_URL
                pwa_parsed = urlparse(PWA_BASE_URL)
                base_url = urlunparse((pwa_parsed.scheme, pwa_parsed.netloc, '', '', '', ''))
            
            logger.info(f"Загрузка проектов через OData API (READ-ONLY режим)")
            logger.info(f"Базовый URL: {base_url}")
            
            # Загрузка данных через OData API
            odata_projects = self._load_projects_via_odata(session, base_url)
            
            if odata_projects is None:
                logger.error("Не удалось загрузить проекты через OData API")
                return []
            
            if not odata_projects:
                logger.info("Список проектов пуст (0 записей)")
                return []
            
            logger.info("=== Преобразование данных OData в стандартный формат ===")
            
            # Преобразуем данные OData в стандартный формат
            projects = []
            for odata_project in odata_projects:
                if not isinstance(odata_project, dict):
                    logger.warning(f"Пропущен проект неверного формата: {type(odata_project)}")
                    continue
                
                # Маппинг полей OData на стандартные поля
                project = {}
                
                # Имя проекта
                project_name = (
                    odata_project.get('ProjName') or 
                    odata_project.get('ProjectName') or 
                    odata_project.get('Name') or 
                    odata_project.get('Title') or 
                    'Без названия'
                )
                project['Name'] = project_name
                
                # ID проекта (ProjUid)
                proj_uid = (
                    odata_project.get('ProjUid') or 
                    odata_project.get('Id') or 
                    odata_project.get('ProjectId')
                )
                if proj_uid:
                    project['Id'] = proj_uid
                    project['ProjUid'] = proj_uid
                
                # URL проекта
                project_url = (
                    odata_project.get('ProjectServerUrl') or
                    odata_project.get('Url') or
                    odata_project.get('ProjectAddress')
                )
                
                # Если URL отсутствует, формируем его на основе ProjUid
                if not project_url and proj_uid:
                    # Формируем URL на основе базового адреса и ProjUid
                    project_url = f"{base_url}/Project Detail Pages/Schedule.aspx?ProjUid={proj_uid}"
                
                if project_url:
                    project['ProjectAddress'] = project_url
                    project['Url'] = project_url
                
                # Сохраняем все остальные поля из OData ответа
                for key, value in odata_project.items():
                    if key not in ['ProjName', 'ProjectName', 'Name', 'Title', 'ProjUid', 'Id', 'ProjectId', 
                                   'ProjectServerUrl', 'Url', 'ProjectAddress']:
                        project[key] = value
                
                projects.append(project)
            
            # Обработка результатов с детальным логированием
            logger.info("=== Информация о считанных проектах ===")
            logger.info(f"✓ Успешно загружено и преобразовано проектов: {len(projects)}")
            
            # Логируем примеры записей
            if len(projects) > 0:
                logger.info(f"Примеры записей (первые {min(2, len(projects))}):")
                for i, project in enumerate(projects[:2]):
                    logger.info(f"  Проект #{i+1}:")
                    logger.info(f"    Name: {project.get('Name', 'N/A')}")
                    logger.info(f"    Id: {project.get('Id', 'N/A')}")
                    logger.info(f"    ProjUid: {project.get('ProjUid', 'N/A')}")
                    logger.info(f"    ProjectAddress: {project.get('ProjectAddress', 'N/A')}")
                    logger.info(f"    Все ключи: {list(project.keys())}")
            
            logger.info(f"Общая статистика: найдено {len(projects)} проектов")
            logger.info("=== Конец информации о проектах ===")
            return projects
                
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

