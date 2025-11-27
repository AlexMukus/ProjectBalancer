# Интеграция Cursor с Confluence

Это руководство описывает способы интеграции Cursor с Atlassian Confluence для чтения требований и публикации release notes.

## Способы интеграции

### 1. Через Confluence REST API (Рекомендуется)

Cursor может работать с Confluence через REST API, используя Python скрипты или другие инструменты.

#### Преимущества:
- Полный контроль над данными
- Возможность автоматизации
- Работа с любыми страницами и пространствами

#### Недостатки:
- Требует настройки аутентификации
- Необходимо писать код для взаимодействия

### 2. Через MCP (Model Context Protocol) серверы

Если доступен MCP сервер для Confluence, можно настроить его в Cursor.

#### Настройка MCP сервера:
1. Установите MCP сервер для Confluence (если доступен)
2. Настройте в конфигурации Cursor
3. Используйте через встроенные инструменты

## Настройка через REST API

### Шаг 1: Получение учетных данных

Для работы с Confluence API вам понадобятся:
- **URL вашего Confluence**: `https://your-domain.atlassian.net`
- **Email/Username**: ваш email или username
- **API Token**: создайте в [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)

### Шаг 2: Установка зависимостей

```bash
pip install requests atlassian-python-api
```

Или добавьте в `requirements.txt`:
```
requests>=2.31.0
atlassian-python-api>=3.41.0
```

### Шаг 3: Использование скриптов

См. примеры в файлах:
- `confluence_reader.py` - для чтения страниц и требований
- `confluence_publisher.py` - для публикации release notes

## Примеры использования

### Чтение требований из Confluence

```python
from confluence_reader import ConfluenceReader

reader = ConfluenceReader(
    url="https://your-domain.atlassian.net",
    username="your-email@example.com",
    api_token="your-api-token"
)

# Чтение страницы с требованиями
requirements = reader.get_page_content("PROJECT", "Requirements Page Title")
print(requirements)
```

### Публикация Release Notes

```python
from confluence_publisher import ConfluencePublisher

publisher = ConfluencePublisher(
    url="https://your-domain.atlassian.net",
    username="your-email@example.com",
    api_token="your-api-token"
)

# Создание release notes
release_notes = {
    "title": "Release v1.2.0",
    "version": "1.2.0",
    "date": "2024-01-15",
    "features": [
        "Новая функция анализа ресурсов",
        "Улучшенный интерфейс"
    ],
    "bugfixes": [
        "Исправлена ошибка расчета нагрузки"
    ]
}

publisher.publish_release_notes("PROJECT", release_notes)
```

## Использование в Cursor

### Вариант 1: Прямое использование скриптов

Вы можете вызывать скрипты напрямую из терминала Cursor:

```bash
python confluence_reader.py --space PROJECT --page "Requirements"
python confluence_publisher.py --space PROJECT --version 1.2.0
```

### Вариант 2: Интеграция в код проекта

Импортируйте модули в ваш код:

```python
from confluence_reader import ConfluenceReader
from confluence_publisher import ConfluencePublisher

# Используйте в вашем приложении
```

### Вариант 3: Использование через AI в Cursor

Вы можете попросить Cursor AI:
- "Прочитай требования из Confluence страницы X"
- "Создай release notes для версии 1.2.0 и опубликуй в Confluence"
- "Найди все страницы с требованиями в пространстве PROJECT"

AI сможет использовать созданные скрипты для выполнения этих задач.

## Переменные окружения

Для безопасности рекомендуется использовать переменные окружения:

```bash
export CONFLUENCE_URL="https://your-domain.atlassian.net"
export CONFLUENCE_USERNAME="your-email@example.com"
export CONFLUENCE_API_TOKEN="your-api-token"
```

Или создайте файл `.env`:
```
CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_USERNAME=your-email@example.com
CONFLUENCE_API_TOKEN=your-api-token
```

## Безопасность

⚠️ **Важно:**
- Никогда не коммитьте API токены в git
- Используйте `.gitignore` для файлов с секретами
- Используйте переменные окружения или секретные менеджеры
- Ограничьте права доступа API токена только необходимыми операциями

## Дополнительные ресурсы

- [Confluence REST API Documentation](https://developer.atlassian.com/cloud/confluence/rest/)
- [Atlassian Python API Library](https://atlassian-python-api.readthedocs.io/)
- [Cursor Documentation](https://docs.cursor.com/)

## Troubleshooting

### Ошибка аутентификации
- Проверьте правильность URL, username и API token
- Убедитесь, что API token активен
- Проверьте права доступа к пространству

### Страница не найдена
- Проверьте правильность названия страницы (регистр важен)
- Убедитесь, что у вас есть доступ к пространству
- Используйте точное название страницы или ID страницы

### Ошибки при публикации
- Проверьте права на создание/редактирование страниц
- Убедитесь, что формат контента соответствует требованиям Confluence
- Проверьте, что пространство существует
