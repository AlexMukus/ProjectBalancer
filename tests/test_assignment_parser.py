"""
Тесты для модуля assignment_parser.py
"""
import pytest
import io
from lxml import etree
from assignment_parser import parse_assignments
from resource_parser import parse_resources
from msproject_utils import find_elements, get_text, make_tag


class TestParseAssignments:
    """Тесты для функции parse_assignments"""
    
    def test_parse_assignments_basic(self, sample_resources, sample_tasks):
        """Тест парсинга базовых назначений"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
            <Units>1</Units>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        assert len(assignments) == 1
        assert assignments[0]['task_id'] == '1'
        assert assignments[0]['resource_name'] == 'Resource 1'
        assert assignments[0]['work'] == 'PT40H0M0S'
        assert assignments[0]['units'] == '1'
    
    def test_parse_assignments_with_resource_name(self, sample_resources, sample_tasks):
        """Тест парсинга назначений с ResourceName в XML"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <ResourceName>Direct Resource Name</ResourceName>
            <Work>PT40H0M0S</Work>
            <Units>1</Units>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        assert len(assignments) == 1
        # ResourceName должен быть использован напрямую из XML
        assert assignments[0]['resource_name'] == 'Direct Resource Name'
    
    def test_parse_assignments_missing_task_uid(self, sample_resources, sample_tasks):
        """Тест обработки назначений с отсутствующим TaskUID"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID></TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        # Назначение должно быть пропущено
        assert len(assignments) == 0
    
    def test_parse_assignments_missing_resource_uid(self, sample_resources, sample_tasks):
        """Тест обработки назначений с отсутствующим ResourceUID"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID></ResourceUID>
            <Work>PT40H0M0S</Work>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        # Назначение должно быть пропущено
        assert len(assignments) == 0
    
    def test_parse_assignments_nonexistent_resource(self, sample_resources, sample_tasks):
        """Тест обработки назначений с несуществующим ресурсом"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>999</ResourceUID>
            <Work>PT40H0M0S</Work>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        # Назначение должно быть пропущено
        assert len(assignments) == 0
    
    def test_parse_assignments_nonexistent_task(self, sample_resources, sample_tasks):
        """Тест обработки назначений с несуществующей задачей"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>999</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        # Назначение должно быть пропущено
        assert len(assignments) == 0
    
    def test_parse_assignments_missing_units(self, sample_resources, sample_tasks):
        """Тест обработки назначений без Units (должен использоваться default)"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        assert len(assignments) == 1
        assert assignments[0]['units'] == '1.0'  # default value
    
    def test_parse_assignments_multiple(self, sample_resources, sample_tasks):
        """Тест парсинга множественных назначений"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
            <Units>1</Units>
        </Assignment>
        <Assignment>
            <UID>2</UID>
            <TaskUID>2</TaskUID>
            <ResourceUID>2</ResourceUID>
            <Work>PT40H0M0S</Work>
            <Units>1</Units>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        assert len(assignments) == 2
        assert assignments[0]['task_id'] == '1'
        assert assignments[1]['task_id'] == '2'
    
    def test_parse_assignments_task_info_included(self, sample_resources, sample_tasks):
        """Тест что информация о задаче включена в назначение"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
        <Assignment>
            <UID>1</UID>
            <TaskUID>1</TaskUID>
            <ResourceUID>1</ResourceUID>
            <Work>PT40H0M0S</Work>
            <Units>1</Units>
        </Assignment>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        
        assert len(assignments) == 1
        assert 'task_id' in assignments[0]
        assert 'task_name' in assignments[0]
        assert 'task_start' in assignments[0]
        assert 'task_finish' in assignments[0]
        assert assignments[0]['task_name'] == 'Task 1'
    
    def test_parse_assignments_sample_xml(self, sample_xml_root, sample_namespace):
        """Тест парсинга назначений из sample_project.xml"""
        # Сначала парсим ресурсы и задачи
        resources = parse_resources(sample_xml_root, sample_namespace, filter_inactive=True)
        
        # Парсим задачи (упрощенная версия для теста)
        task_elements = find_elements(sample_xml_root, 'Task', sample_namespace)
        tasks = []
        for task in task_elements:
            task_id = get_text(task, make_tag('UID', sample_namespace), sample_namespace)
            name = get_text(task, make_tag('Name', sample_namespace), sample_namespace)
            if task_id and name:
                tasks.append({
                    'id': str(task_id),
                    'name': name,
                    'start': get_text(task, make_tag('Start', sample_namespace), sample_namespace),
                    'finish': get_text(task, make_tag('Finish', sample_namespace), sample_namespace),
                })
        
        # Парсим назначения
        assignments = parse_assignments(sample_xml_root, sample_namespace, resources, tasks)
        
        # В sample_project.xml должно быть 8 назначений
        assert len(assignments) == 8
        
        # Проверяем структуру первого назначения
        assert 'task_id' in assignments[0]
        assert 'task_name' in assignments[0]
        assert 'resource_name' in assignments[0]
        assert 'work' in assignments[0]
        assert 'units' in assignments[0]
    
    def test_parse_assignments_empty_xml(self, sample_resources, sample_tasks):
        """Тест парсинга пустого XML"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Assignments>
    </Assignments>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        assignments = parse_assignments(root, namespace, sample_resources, sample_tasks)
        assert len(assignments) == 0

