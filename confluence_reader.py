"""
Модуль для чтения данных из Confluence через REST API.
Используется для получения требований и другой документации.
"""

import os
import requests
from typing import Optional, Dict, List
from urllib.parse import quote


class ConfluenceReader:
    """Класс для чтения страниц и контента из Confluence."""
    
    def __init__(self, url: str, username: str, api_token: str):
        """
        Инициализация читателя Confluence.
        
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
    
    def get_page_by_title(self, space_key: str, page_title: str) -> Optional[Dict]:
        """
        Получить страницу по названию.
        
        Args:
            space_key: Ключ пространства (например, 'PROJECT')
            page_title: Название страницы
            
        Returns:
            Словарь с данными страницы или None
        """
        url = f"{self.base_url}/content"
        params = {
            'spaceKey': space_key,
            'title': page_title,
            'expand': 'body.storage,version'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        results = response.json().get('results', [])
        if results:
            return results[0]
        return None
    
    def get_page_by_id(self, page_id: str) -> Optional[Dict]:
        """
        Получить страницу по ID.
        
        Args:
            page_id: ID страницы в Confluence
            
        Returns:
            Словарь с данными страницы или None
        """
        url = f"{self.base_url}/content/{page_id}"
        params = {
            'expand': 'body.storage,version,ancestors'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def get_page_content(self, space_key: str, page_title: str) -> Optional[str]:
        """
        Получить содержимое страницы в виде текста.
        
        Args:
            space_key: Ключ пространства
            page_title: Название страницы
            
        Returns:
            Текст содержимого страницы или None
        """
        page = self.get_page_by_title(space_key, page_title)
        if page:
            return page.get('body', {}).get('storage', {}).get('value', '')
        return None
    
    def search_pages(self, space_key: str, query: str, limit: int = 25) -> List[Dict]:
        """
        Поиск страниц в пространстве.
        
        Args:
            space_key: Ключ пространства
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных страниц
        """
        url = f"{self.base_url}/content/search"
        params = {
            'cql': f'space = {space_key} AND text ~ "{query}"',
            'limit': limit,
            'expand': 'body.storage'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json().get('results', [])
    
    def get_pages_by_label(self, space_key: str, label: str) -> List[Dict]:
        """
        Получить страницы по метке.
        
        Args:
            space_key: Ключ пространства
            label: Метка для поиска
            
        Returns:
            Список страниц с указанной меткой
        """
        url = f"{self.base_url}/content/search"
        params = {
            'cql': f'space = {space_key} AND label = "{label}"',
            'expand': 'body.storage'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json().get('results', [])
    
    def get_child_pages(self, page_id: str) -> List[Dict]:
        """
        Получить дочерние страницы.
        
        Args:
            page_id: ID родительской страницы
            
        Returns:
            Список дочерних страниц
        """
        url = f"{self.base_url}/content/{page_id}/child/page"
        params = {
            'expand': 'body.storage'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json().get('results', [])
    
    def extract_text_from_html(self, html_content: str) -> str:
        """
        Извлечь текст из HTML содержимого Confluence.
        
        Args:
            html_content: HTML содержимое страницы
            
        Returns:
            Текст без HTML разметки
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        except ImportError:
            # Простое извлечение текста без BeautifulSoup
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()


def main():
    """Пример использования ConfluenceReader."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Чтение страниц из Confluence')
    parser.add_argument('--url', default=os.getenv('CONFLUENCE_URL'),
                       help='URL Confluence')
    parser.add_argument('--username', default=os.getenv('CONFLUENCE_USERNAME'),
                       help='Username или email')
    parser.add_argument('--api-token', default=os.getenv('CONFLUENCE_API_TOKEN'),
                       help='API токен')
    parser.add_argument('--space', required=True,
                       help='Ключ пространства')
    parser.add_argument('--page', required=True,
                       help='Название страницы')
    parser.add_argument('--text-only', action='store_true',
                       help='Вывести только текст без HTML')
    
    args = parser.parse_args()
    
    if not all([args.url, args.username, args.api_token]):
        print("Ошибка: Необходимо указать URL, username и API token")
        print("Используйте переменные окружения или аргументы командной строки")
        return
    
    reader = ConfluenceReader(args.url, args.username, args.api_token)
    
    if args.text_only:
        content = reader.get_page_content(args.space, args.page)
        if content:
            text = reader.extract_text_from_html(content)
            print(text)
        else:
            print(f"Страница '{args.page}' не найдена в пространстве '{args.space}'")
    else:
        page = reader.get_page_by_title(args.space, args.page)
        if page:
            print(f"Заголовок: {page.get('title')}")
            print(f"ID: {page.get('id')}")
            print(f"Версия: {page.get('version', {}).get('number')}")
            print("\nСодержимое:")
            content = page.get('body', {}).get('storage', {}).get('value', '')
            text = reader.extract_text_from_html(content)
            print(text)
        else:
            print(f"Страница '{args.page}' не найдена в пространстве '{args.space}'")


if __name__ == '__main__':
    main()
