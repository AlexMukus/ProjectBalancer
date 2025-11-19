"""
Модуль для публикации данных в Confluence через REST API.
Используется для создания и обновления release notes и другой документации.
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime


class ConfluencePublisher:
    """Класс для публикации контента в Confluence."""
    
    def __init__(self, url: str, username: str, api_token: str):
        """
        Инициализация публикатора Confluence.
        
        Args:
            url: URL вашего Confluence (например, https://your-domain.atlassian.net)
            username: Email или username для аутентификации
            api_token: API токен из Atlassian Account Settings
        """
        self.url = url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.base_url = f"{self.url}/wiki/rest/api"
        self.session = requests.Session()
        self.session.auth = (username, api_token)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def create_page(self, space_key: str, title: str, content: str, 
                   parent_id: Optional[str] = None) -> Dict:
        """
        Создать новую страницу в Confluence.
        
        Args:
            space_key: Ключ пространства
            title: Заголовок страницы
            content: Содержимое в формате Confluence Storage Format (HTML)
            parent_id: ID родительской страницы (опционально)
            
        Returns:
            Словарь с данными созданной страницы
        """
        url = f"{self.base_url}/content"
        
        data = {
            'type': 'page',
            'title': title,
            'space': {'key': space_key},
            'body': {
                'storage': {
                    'value': content,
                    'representation': 'storage'
                }
            }
        }
        
        if parent_id:
            data['ancestors'] = [{'id': parent_id}]
        
        response = self.session.post(url, json=data)
        response.raise_for_status()
        
        return response.json()
    
    def update_page(self, page_id: str, title: str, content: str, 
                   version: int) -> Dict:
        """
        Обновить существующую страницу.
        
        Args:
            page_id: ID страницы для обновления
            title: Новый заголовок
            content: Новое содержимое
            version: Текущая версия страницы (должна быть увеличена на 1)
            
        Returns:
            Словарь с данными обновленной страницы
        """
        url = f"{self.base_url}/content/{page_id}"
        
        data = {
            'id': page_id,
            'type': 'page',
            'title': title,
            'version': {'number': version},
            'body': {
                'storage': {
                    'value': content,
                    'representation': 'storage'
                }
            }
        }
        
        response = self.session.put(url, json=data)
        response.raise_for_status()
        
        return response.json()
    
    def get_page_by_title(self, space_key: str, page_title: str) -> Optional[Dict]:
        """Получить страницу по названию."""
        url = f"{self.base_url}/content"
        params = {
            'spaceKey': space_key,
            'title': page_title,
            'expand': 'version'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        results = response.json().get('results', [])
        if results:
            return results[0]
        return None
    
    def create_or_update_page(self, space_key: str, title: str, content: str,
                             parent_id: Optional[str] = None) -> Dict:
        """
        Создать страницу или обновить существующую.
        
        Args:
            space_key: Ключ пространства
            title: Заголовок страницы
            content: Содержимое страницы
            parent_id: ID родительской страницы (опционально)
            
        Returns:
            Словарь с данными страницы
        """
        existing_page = self.get_page_by_title(space_key, title)
        
        if existing_page:
            page_id = existing_page['id']
            version = existing_page['version']['number'] + 1
            return self.update_page(page_id, title, content, version)
        else:
            return self.create_page(space_key, title, content, parent_id)
    
    def format_release_notes_html(self, release_data: Dict) -> str:
        """
        Форматировать release notes в HTML для Confluence.
        
        Args:
            release_data: Словарь с данными релиза:
                - title: Заголовок релиза
                - version: Версия
                - date: Дата релиза
                - features: Список новых функций
                - bugfixes: Список исправлений
                - improvements: Список улучшений (опционально)
                - breaking_changes: Список breaking changes (опционально)
                
        Returns:
            HTML содержимое для Confluence
        """
        html_parts = []
        
        # Заголовок
        html_parts.append(f'<h1>{release_data.get("title", f"Release {release_data.get("version", "")}")}</h1>')
        
        # Метаинформация
        html_parts.append('<p>')
        html_parts.append(f'<strong>Версия:</strong> {release_data.get("version", "N/A")}<br/>')
        html_parts.append(f'<strong>Дата:</strong> {release_data.get("date", datetime.now().strftime("%Y-%m-%d"))}')
        html_parts.append('</p>')
        
        html_parts.append('<hr/>')
        
        # Новые функции
        if release_data.get('features'):
            html_parts.append('<h2>✨ Новые функции</h2>')
            html_parts.append('<ul>')
            for feature in release_data['features']:
                html_parts.append(f'<li>{feature}</li>')
            html_parts.append('</ul>')
        
        # Улучшения
        if release_data.get('improvements'):
            html_parts.append('<h2>🚀 Улучшения</h2>')
            html_parts.append('<ul>')
            for improvement in release_data['improvements']:
                html_parts.append(f'<li>{improvement}</li>')
            html_parts.append('</ul>')
        
        # Исправления
        if release_data.get('bugfixes'):
            html_parts.append('<h2>🐛 Исправления</h2>')
            html_parts.append('<ul>')
            for bugfix in release_data['bugfixes']:
                html_parts.append(f'<li>{bugfix}</li>')
            html_parts.append('</ul>')
        
        # Breaking changes
        if release_data.get('breaking_changes'):
            html_parts.append('<h2>⚠️ Breaking Changes</h2>')
            html_parts.append('<ul>')
            for change in release_data['breaking_changes']:
                html_parts.append(f'<li>{change}</li>')
            html_parts.append('</ul>')
        
        return '\n'.join(html_parts)
    
    def publish_release_notes(self, space_key: str, release_data: Dict,
                            parent_page_title: Optional[str] = None) -> Dict:
        """
        Опубликовать release notes в Confluence.
        
        Args:
            space_key: Ключ пространства
            release_data: Данные релиза (см. format_release_notes_html)
            parent_page_title: Название родительской страницы (опционально)
            
        Returns:
            Словарь с данными созданной/обновленной страницы
        """
        title = release_data.get('title', f"Release {release_data.get('version', '')}")
        content = self.format_release_notes_html(release_data)
        
        parent_id = None
        if parent_page_title:
            parent_page = self.get_page_by_title(space_key, parent_page_title)
            if parent_page:
                parent_id = parent_page['id']
        
        return self.create_or_update_page(space_key, title, content, parent_id)
    
    def add_labels(self, page_id: str, labels: List[str]) -> Dict:
        """
        Добавить метки к странице.
        
        Args:
            page_id: ID страницы
            labels: Список меток для добавления
            
        Returns:
            Словарь с результатом операции
        """
        url = f"{self.base_url}/content/{page_id}/label"
        
        data = [{'prefix': 'global', 'name': label} for label in labels]
        
        response = self.session.post(url, json=data)
        response.raise_for_status()
        
        return response.json()


def main():
    """Пример использования ConfluencePublisher."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Публикация release notes в Confluence')
    parser.add_argument('--url', default=os.getenv('CONFLUENCE_URL'),
                       help='URL Confluence')
    parser.add_argument('--username', default=os.getenv('CONFLUENCE_USERNAME'),
                       help='Username или email')
    parser.add_argument('--api-token', default=os.getenv('CONFLUENCE_API_TOKEN'),
                       help='API токен')
    parser.add_argument('--space', required=True,
                       help='Ключ пространства')
    parser.add_argument('--version', required=True,
                       help='Версия релиза')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'),
                       help='Дата релиза (YYYY-MM-DD)')
    parser.add_argument('--title', help='Заголовок страницы')
    parser.add_argument('--features', nargs='+', default=[],
                       help='Список новых функций')
    parser.add_argument('--bugfixes', nargs='+', default=[],
                       help='Список исправлений')
    parser.add_argument('--improvements', nargs='+', default=[],
                       help='Список улучшений')
    parser.add_argument('--parent', help='Название родительской страницы')
    parser.add_argument('--json-file', help='Путь к JSON файлу с данными релиза')
    
    args = parser.parse_args()
    
    if not all([args.url, args.username, args.api_token]):
        print("Ошибка: Необходимо указать URL, username и API token")
        print("Используйте переменные окружения или аргументы командной строки")
        return
    
    publisher = ConfluencePublisher(args.url, args.username, args.api_token)
    
    if args.json_file:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            release_data = json.load(f)
    else:
        release_data = {
            'version': args.version,
            'date': args.date,
            'title': args.title or f"Release {args.version}",
            'features': args.features,
            'bugfixes': args.bugfixes,
            'improvements': args.improvements
        }
    
    result = publisher.publish_release_notes(
        args.space,
        release_data,
        args.parent
    )
    
    print(f"✅ Release notes опубликованы!")
    print(f"Заголовок: {result.get('title')}")
    print(f"ID: {result.get('id')}")
    print(f"URL: {publisher.url}/wiki{result.get('_links', {}).get('webui', '')}")


if __name__ == '__main__':
    main()
