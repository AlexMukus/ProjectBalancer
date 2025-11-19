# Быстрый старт: Интеграция Cursor с Confluence

## Шаг 1: Получение API токена

1. Перейдите на https://id.atlassian.com/manage-profile/security/api-tokens
2. Нажмите "Create API token"
3. Дайте токену имя (например, "Cursor Integration")
4. Скопируйте созданный токен (он показывается только один раз!)

## Шаг 2: Установка зависимостей

```bash
pip install -r requirements_confluence.txt
```

## Шаг 3: Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Отредактируйте `.env` и укажите свои данные:
- `CONFLUENCE_URL` - URL вашего Confluence
- `CONFLUENCE_USERNAME` - ваш email
- `CONFLUENCE_API_TOKEN` - токен из шага 1

## Шаг 4: Использование

### Чтение требований из Confluence

```bash
python confluence_reader.py \
  --space PROJECT \
  --page "Требования проекта" \
  --text-only
```

### Публикация Release Notes

#### Вариант 1: Через командную строку

```bash
python confluence_publisher.py \
  --space PROJECT \
  --version 1.2.0 \
  --date 2024-01-15 \
  --features "Новая функция" "Еще одна функция" \
  --bugfixes "Исправлена ошибка" \
  --parent "Release Notes"
```

#### Вариант 2: Через JSON файл

```bash
python confluence_publisher.py \
  --space PROJECT \
  --json-file example_release_notes.json \
  --parent "Release Notes"
```

### Использование в Python коде

```python
from confluence_reader import ConfluenceReader
from confluence_publisher import ConfluencePublisher
import os

# Инициализация
reader = ConfluenceReader(
    url=os.getenv('CONFLUENCE_URL'),
    username=os.getenv('CONFLUENCE_USERNAME'),
    api_token=os.getenv('CONFLUENCE_API_TOKEN')
)

# Чтение требований
requirements = reader.get_page_content('PROJECT', 'Требования проекта')
print(requirements)

# Публикация release notes
publisher = ConfluencePublisher(
    url=os.getenv('CONFLUENCE_URL'),
    username=os.getenv('CONFLUENCE_USERNAME'),
    api_token=os.getenv('CONFLUENCE_API_TOKEN')
)

release_data = {
    'version': '1.2.0',
    'date': '2024-01-15',
    'title': 'Release v1.2.0',
    'features': ['Новая функция'],
    'bugfixes': ['Исправлена ошибка']
}

publisher.publish_release_notes('PROJECT', release_data, 'Release Notes')
```

## Использование с Cursor AI

Теперь вы можете использовать Cursor AI для работы с Confluence:

1. **Чтение требований:**
   - "Прочитай требования из Confluence страницы 'Требования проекта' в пространстве PROJECT"
   - "Найди все страницы с меткой 'requirements' в пространстве PROJECT"

2. **Публикация release notes:**
   - "Создай release notes для версии 1.2.0 с функциями X, Y, Z и опубликуй в Confluence"
   - "Обнови release notes в Confluence с информацией о новом релизе"

3. **Анализ документации:**
   - "Проанализируй требования из Confluence и создай план разработки"
   - "Сравни требования из разных страниц Confluence"

## Troubleshooting

### Ошибка: "401 Unauthorized"
- Проверьте правильность username и API token
- Убедитесь, что токен активен

### Ошибка: "404 Not Found"
- Проверьте правильность URL Confluence
- Убедитесь, что пространство существует

### Ошибка: "403 Forbidden"
- Проверьте права доступа к пространству
- Убедитесь, что у вас есть права на создание/редактирование страниц

## Дополнительная информация

См. полную документацию в `CONFLUENCE_INTEGRATION.md`
