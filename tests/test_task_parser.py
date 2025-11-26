"""
Тесты для метода _parse_tasks из app.py
"""
import pytest
import io
from lxml import etree
from app import MSProjectParser


class TestParseTasks:
    """Тесты для метода _parse_tasks"""
    
    def test_parse_tasks_basic(self, task_xml_minimal):
        """Тест парсинга базовых задач"""
        root, namespace = task_xml_minimal
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 2
        assert tasks[0]['id'] == '1'
        assert tasks[0]['name'] == 'Task 1'
        assert tasks[0]['start'] == '2025-01-01T08:00:00'
        assert tasks[0]['finish'] == '2025-01-05T17:00:00'
        assert 'duration' in tasks[0]
        assert 'work' in tasks[0]
        assert 'predecessors' in tasks[0]
    
    def test_parse_tasks_with_dependencies(self, task_xml_with_dependencies):
        """Тест парсинга задач с зависимостями"""
        root, namespace = task_xml_with_dependencies
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 2
        
        # Первая задача не имеет зависимостей
        task1 = next(t for t in tasks if t['id'] == '1')
        assert len(task1['predecessors']) == 0
        
        # Вторая задача имеет зависимость от первой
        task2 = next(t for t in tasks if t['id'] == '2')
        assert len(task2['predecessors']) == 1
        assert task2['predecessors'][0] == '1'
    
    def test_parse_tasks_missing_name(self):
        """Тест обработки задачи без имени (должно генерироваться автоматически)"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Start>2025-01-01T08:00:00</Start>
            <Finish>2025-01-05T17:00:00</Finish>
        </Task>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 1
        assert tasks[0]['name'] == 'Задача #1'
    
    def test_parse_tasks_missing_uid(self):
        """Тест обработки задачи без UID (должна быть пропущена)"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <Name>Task Without UID</Name>
            <Start>2025-01-01T08:00:00</Start>
            <Finish>2025-01-05T17:00:00</Finish>
        </Task>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        # Задача без UID должна быть пропущена
        assert len(tasks) == 0
    
    def test_parse_tasks_missing_optional_fields(self):
        """Тест обработки задачи с отсутствующими опциональными полями"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Name>Task 1</Name>
        </Task>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 1
        assert tasks[0]['id'] == '1'
        assert tasks[0]['name'] == 'Task 1'
        # Опциональные поля должны быть пустыми строками
        assert tasks[0]['start'] == ''
        assert tasks[0]['finish'] == ''
        assert tasks[0]['duration'] == ''
        assert tasks[0]['work'] == ''
    
    def test_parse_tasks_multiple_predecessors(self):
        """Тест парсинга задачи с множественными зависимостями"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Name>Task 1</Name>
        </Task>
        <Task>
            <UID>2</UID>
            <Name>Task 2</Name>
        </Task>
        <Task>
            <UID>3</UID>
            <Name>Task 3</Name>
            <PredecessorLink>
                <PredecessorUID>1</PredecessorUID>
            </PredecessorLink>
            <PredecessorLink>
                <PredecessorUID>2</PredecessorUID>
            </PredecessorLink>
        </Task>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 3
        
        task3 = next(t for t in tasks if t['id'] == '3')
        assert len(task3['predecessors']) == 2
        assert '1' in task3['predecessors']
        assert '2' in task3['predecessors']
    
    def test_parse_tasks_empty_predecessor_uid(self):
        """Тест обработки PredecessorLink с пустым PredecessorUID"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Name>Task 1</Name>
            <PredecessorLink>
                <PredecessorUID></PredecessorUID>
            </PredecessorLink>
        </Task>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert len(tasks) == 1
        assert len(tasks[0]['predecessors']) == 0  # Пустой PredecessorUID должен быть пропущен
    
    def test_parse_tasks_id_as_string(self, task_xml_minimal):
        """Тест что ID всегда преобразуется в строку"""
        root, namespace = task_xml_minimal
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        assert isinstance(tasks[0]['id'], str)
        assert isinstance(tasks[1]['id'], str)
    
    def test_parse_tasks_predecessors_as_strings(self, task_xml_with_dependencies):
        """Тест что предшественники преобразуются в строки"""
        root, namespace = task_xml_with_dependencies
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        
        task2 = next(t for t in tasks if t['id'] == '2')
        assert all(isinstance(p, str) for p in task2['predecessors'])
    
    def test_parse_tasks_sample_xml(self, sample_xml_root, sample_namespace):
        """Тест парсинга задач из sample_project.xml"""
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(sample_xml_root, sample_namespace)
        
        # В sample_project.xml должно быть 8 задач
        assert len(tasks) == 8
        
        # Проверяем структуру первой задачи
        assert 'id' in tasks[0]
        assert 'name' in tasks[0]
        assert 'start' in tasks[0]
        assert 'finish' in tasks[0]
        assert 'duration' in tasks[0]
        assert 'work' in tasks[0]
        assert 'predecessors' in tasks[0]
        
        # Проверяем, что все задачи имеют уникальные ID
        ids = [t['id'] for t in tasks]
        assert len(ids) == len(set(ids))
    
    def test_parse_tasks_empty_xml(self):
        """Тест парсинга пустого XML"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
    </Tasks>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        parser = MSProjectParser(b'')
        tasks = parser._parse_tasks(root, namespace)
        assert len(tasks) == 0

