"""
Модуль для подключения к MS Project Server через REST API
Управляет подключением с NTLM аутентификацией

ВАЖНО: ВСЕ ОПЕРАЦИИ С СЕРВЕРОМ СТРОГО ТОЛЬКО ДЛЯ ЧТЕНИЯ!
Изменение данных на сервере строго запрещено.
Допускается только чтение данных через GET запросы.
"""
import requests
from requests_ntlm import HttpNtlmAuth  # type: ignore
from msproject_utils import setup_logger

# Константы подключения по умолчанию
DEFAULT_SERVER_URL = "http://tpch-app04/Projects.aspx"
DEFAULT_DOMAIN = "TECHPROM"

# Настройка логирования
logger = setup_logger(__name__)

# Константа для обеспечения read-only режима
READ_ONLY_MODE = True  # Строго только чтение, изменения запрещены


class MSProjectServerConnection:
    """
    Класс для управления подключением к MS Project Server
    
    Обеспечивает подключение и отключение по команде пользователя
    с логированием всех операций в консоль.
    
    ВАЖНО: Класс работает строго в режиме ТОЛЬКО ДЛЯ ЧТЕНИЯ.
    Все операции выполняются исключительно через GET запросы.
    Изменение данных на сервере строго запрещено.
    """
    
    def __init__(self):
        """
        Инициализация объекта подключения
        
        ВАЖНО: Подключение работает только в режиме чтения.
        """
        self._session = None
        self._server_url = None
        self._is_connected = False
        if not READ_ONLY_MODE:
            logger.warning("ВНИМАНИЕ: READ_ONLY_MODE отключен! Это недопустимо.")
    
    def connect(self, server_url, username, password, domain=None):
        """
        Установка соединения с MS Project Server по команде пользователя
        
        ВАЖНО: Подключение используется только для чтения данных.
        Изменение данных на сервере строго запрещено.
        
        Args:
            server_url: URL сервера (например, http://server/ProjectServer)
            username: Имя пользователя
            password: Пароль
            domain: Домен (опционально)
        
        Returns:
            bool: True при успешном подключении, False при ошибке
        """
        try:
            # Если уже подключено, сначала отключаемся
            if self._is_connected:
                logger.warning("Уже подключено к серверу. Сначала выполните отключение.")
                return False
            
            logger.info(f"Попытка подключения к серверу: {server_url} (READ-ONLY режим)")
            
            # Нормализация URL (убираем завершающий слэш)
            server_url = server_url.rstrip('/')
            self._server_url = server_url
            
            # Создание сессии с NTLM аутентификацией
            self._session = requests.Session()
            
            # Формирование учетных данных для NTLM
            if domain:
                ntlm_username = f"{domain}\\{username}"
            else:
                ntlm_username = username
            
            self._session.auth = HttpNtlmAuth(ntlm_username, password)
            
            # Тестовый запрос для проверки подключения
            # ВАЖНО: Используется ТОЛЬКО GET запрос для чтения
            # Используем корневой эндпоинт Project Server
            test_url = f"{server_url}/ProjectData.svc"
            
            try:
                # ВАЖНО: Только GET запрос - никаких изменений данных
                response = self._session.get(test_url, timeout=10)
                
                # Проверка статуса ответа
                if response.status_code == 200:
                    # Успешное подключение
                    self._is_connected = True
                    logger.info(f"Успешно подключено к серверу: {server_url} (READ-ONLY режим)")
                    return True
                elif response.status_code == 401:
                    # Ошибка аутентификации
                    logger.error(f"Ошибка аутентификации. Проверьте учетные данные. Статус: {response.status_code}")
                    self._session.close()
                    self._session = None
                    return False
                elif 200 <= response.status_code < 300:
                    # Другие успешные статусы
                    self._is_connected = True
                    logger.info(f"Успешно подключено к серверу: {server_url} (READ-ONLY режим)")
                    return True
                else:
                    logger.error(f"Ошибка подключения. Статус ответа: {response.status_code}")
                    self._session.close()
                    self._session = None
                    return False
                    
            except requests.exceptions.Timeout:
                logger.error("Ошибка подключения: превышено время ожидания ответа от сервера")
                self._session.close()
                self._session = None
                return False
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ошибка подключения: не удалось установить соединение с сервером. {str(e)}")
                self._session.close()
                self._session = None
                return False
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка подключения: {str(e)}")
                self._session.close()
                self._session = None
                return False
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении: {str(e)}")
            if self._session:
                self._session.close()
                self._session = None
            self._is_connected = False
            return False
    
    def disconnect(self):
        """
        Разрыв соединения с сервером по команде пользователя
        
        Логирует успешное отключение в консоль.
        
        ВАЖНО: Операция не изменяет данные на сервере.
        """
        if not self._is_connected:
            logger.warning("Попытка отключения при отсутствии активного подключения")
            return
        
        try:
            if self._session:
                self._session.close()
                self._session = None
            
            server_url = self._server_url
            self._server_url = None
            self._is_connected = False
            
            logger.info(f"Успешно отключено от сервера: {server_url}")
            
        except Exception as e:
            logger.error(f"Ошибка при отключении: {str(e)}")
            # Принудительно очищаем состояние даже при ошибке
            self._session = None
            self._server_url = None
            self._is_connected = False
    
    def is_connected(self):
        """
        Проверка статуса подключения
        
        Returns:
            bool: True если подключено, False если нет
        """
        return self._is_connected and self._session is not None
    
    def get_session(self):
        """
        Получение активной сессии для использования в других модулях
        
        ВАЖНО: Сессия должна использоваться ТОЛЬКО для GET запросов (чтение).
        POST, PUT, PATCH, DELETE запросы строго запрещены.
        
        Returns:
            requests.Session: Активная сессия или None если не подключено
        """
        if self.is_connected():
            return self._session
        return None
    
    def get_server_url(self):
        """
        Получение URL подключенного сервера
        
        Returns:
            str: URL сервера или None если не подключено
        """
        if self.is_connected():
            return self._server_url
        return None

