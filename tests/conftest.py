"""
Общие фикстуры для тестов парсинга XML
"""
import pytest
from lxml import etree
import io
import os


@pytest.fixture
def sample_xml_path():
    """Путь к sample_project.xml"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'sample_project.xml')


@pytest.fixture
def sample_xml_root(sample_xml_path):
    """Корневой элемент XML из sample_project.xml"""
    with open(sample_xml_path, 'rb') as f:
        tree = etree.parse(f)
        return tree.getroot()


@pytest.fixture
def sample_namespace(sample_xml_root):
    """Namespace из sample XML"""
    from msproject_utils import get_namespace
    return get_namespace(sample_xml_root)


@pytest.fixture
def xml_with_namespace():
    """XML с namespace"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Name>Test Project</Name>
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Test Resource</Name>
            <MaxUnits>1</MaxUnits>
        </Resource>
    </Resources>
</Project>'''
    return etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()


@pytest.fixture
def xml_without_namespace():
    """XML без namespace"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project>
    <Name>Test Project</Name>
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Test Resource</Name>
            <MaxUnits>1</MaxUnits>
        </Resource>
    </Resources>
</Project>'''
    return etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()


@pytest.fixture
def empty_namespace():
    """Пустой namespace словарь"""
    return {}


@pytest.fixture
def minimal_resource_xml():
    """Минимальный XML с одним ресурсом"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Resource 1</Name>
            <MaxUnits>1.0</MaxUnits>
            <IsInactive>0</IsInactive>
        </Resource>
    </Resources>
</Project>'''
    root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
    namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
    return root, namespace


@pytest.fixture
def resource_xml_with_inactive():
    """XML с активными и неактивными ресурсами"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Active Resource</Name>
            <MaxUnits>1.0</MaxUnits>
            <IsInactive>0</IsInactive>
        </Resource>
        <Resource>
            <UID>2</UID>
            <Name>Inactive Resource</Name>
            <MaxUnits>1.0</MaxUnits>
            <IsInactive>1</IsInactive>
        </Resource>
    </Resources>
</Project>'''
    root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
    namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
    return root, namespace


@pytest.fixture
def resource_xml_with_missing_fields():
    """XML с ресурсами с отсутствующими полями"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Valid Resource</Name>
            <MaxUnits>1.0</MaxUnits>
        </Resource>
        <Resource>
            <UID></UID>
            <Name>No UID Resource</Name>
        </Resource>
        <Resource>
            <UID>2</UID>
            <Name></Name>
        </Resource>
        <Resource>
            <UID>3</UID>
            <Name>No MaxUnits</Name>
        </Resource>
    </Resources>
</Project>'''
    root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
    namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
    return root, namespace


@pytest.fixture
def task_xml_minimal():
    """Минимальный XML с задачами"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Name>Task 1</Name>
            <Start>2025-01-01T08:00:00</Start>
            <Finish>2025-01-05T17:00:00</Finish>
            <Duration>PT40H0M0S</Duration>
        </Task>
        <Task>
            <UID>2</UID>
            <Name>Task 2</Name>
            <Start>2025-01-06T08:00:00</Start>
            <Finish>2025-01-10T17:00:00</Finish>
        </Task>
    </Tasks>
</Project>'''
    root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
    namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
    return root, namespace


@pytest.fixture
def task_xml_with_dependencies():
    """XML с задачами и зависимостями"""
    xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Tasks>
        <Task>
            <UID>1</UID>
            <Name>Task 1</Name>
            <Start>2025-01-01T08:00:00</Start>
            <Finish>2025-01-05T17:00:00</Finish>
        </Task>
        <Task>
            <UID>2</UID>
            <Name>Task 2</Name>
            <Start>2025-01-06T08:00:00</Start>
            <Finish>2025-01-10T17:00:00</Finish>
            <PredecessorLink>
                <PredecessorUID>1</PredecessorUID>
            </PredecessorLink>
        </Task>
    </Tasks>
</Project>'''
    root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
    namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
    return root, namespace


@pytest.fixture
def assignment_xml_minimal():
    """Минимальный XML с назначениями"""
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
    return root, namespace


@pytest.fixture
def sample_resources():
    """Пример списка ресурсов для тестов"""
    return [
        {'id': '1', 'name': 'Resource 1', 'max_units': '1.0', 'is_inactive': '0'},
        {'id': '2', 'name': 'Resource 2', 'max_units': '1.0', 'is_inactive': '0'},
        {'id': '3', 'name': 'Resource 3', 'max_units': '0.5', 'is_inactive': '0'},
    ]


@pytest.fixture
def sample_tasks():
    """Пример списка задач для тестов"""
    return [
        {
            'id': '1',
            'name': 'Task 1',
            'start': '2025-01-01T08:00:00',
            'finish': '2025-01-05T17:00:00',
            'duration': 'PT40H0M0S'
        },
        {
            'id': '2',
            'name': 'Task 2',
            'start': '2025-01-06T08:00:00',
            'finish': '2025-01-10T17:00:00',
            'duration': 'PT40H0M0S'
        },
    ]

