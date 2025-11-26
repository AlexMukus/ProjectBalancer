"""
Тесты для модуля resource_parser.py
"""
import pytest
import io
from lxml import etree
from resource_parser import parse_resources


class TestParseResources:
    """Тесты для функции parse_resources"""
    
    def test_parse_resources_basic(self, minimal_resource_xml):
        """Тест парсинга базовых ресурсов"""
        root, namespace = minimal_resource_xml
        resources = parse_resources(root, namespace, filter_inactive=True)
        
        assert len(resources) == 1
        assert resources[0]['id'] == '1'
        assert resources[0]['name'] == 'Resource 1'
        assert resources[0]['max_units'] == '1.0'
        assert resources[0]['is_inactive'] == '0'
    
    def test_parse_resources_with_inactive_filtered(self, resource_xml_with_inactive):
        """Тест фильтрации неактивных ресурсов"""
        root, namespace = resource_xml_with_inactive
        resources = parse_resources(root, namespace, filter_inactive=True)
        
        # Должен быть только активный ресурс
        assert len(resources) == 1
        assert resources[0]['name'] == 'Active Resource'
        assert resources[0]['is_inactive'] == '0'
    
    def test_parse_resources_with_inactive_not_filtered(self, resource_xml_with_inactive):
        """Тест парсинга без фильтрации неактивных ресурсов"""
        root, namespace = resource_xml_with_inactive
        resources = parse_resources(root, namespace, filter_inactive=False)
        
        # Должны быть оба ресурса
        assert len(resources) == 2
        names = [r['name'] for r in resources]
        assert 'Active Resource' in names
        assert 'Inactive Resource' in names
    
    def test_parse_resources_missing_fields(self, resource_xml_with_missing_fields):
        """Тест обработки ресурсов с отсутствующими полями"""
        root, namespace = resource_xml_with_missing_fields
        resources = parse_resources(root, namespace, filter_inactive=True)
        
        # Должен быть только валидный ресурс (с UID и Name)
        assert len(resources) == 1
        assert resources[0]['name'] == 'Valid Resource'
    
    def test_parse_resources_missing_max_units(self, minimal_resource_xml):
        """Тест обработки ресурса без MaxUnits (должен использоваться default)"""
        root, namespace = minimal_resource_xml
        # Удалим MaxUnits из XML
        resource_elem = root.find('.//{http://schemas.microsoft.com/project}Resource')
        max_units_elem = resource_elem.find('{http://schemas.microsoft.com/project}MaxUnits')
        if max_units_elem is not None:
            resource_elem.remove(max_units_elem)
        
        resources = parse_resources(root, namespace, filter_inactive=True)
        assert len(resources) == 1
        assert resources[0]['max_units'] == '1.0'  # default value
    
    def test_parse_resources_missing_is_inactive(self, minimal_resource_xml):
        """Тест обработки ресурса без IsInactive (должен использоваться default)"""
        root, namespace = minimal_resource_xml
        # Удалим IsInactive из XML
        resource_elem = root.find('.//{http://schemas.microsoft.com/project}Resource')
        is_inactive_elem = resource_elem.find('{http://schemas.microsoft.com/project}IsInactive')
        if is_inactive_elem is not None:
            resource_elem.remove(is_inactive_elem)
        
        resources = parse_resources(root, namespace, filter_inactive=True)
        assert len(resources) == 1
        assert resources[0]['is_inactive'] == '0'  # default value
    
    def test_parse_resources_without_namespace(self, xml_without_namespace):
        """Тест парсинга ресурсов без namespace"""
        namespace = {}
        resources = parse_resources(xml_without_namespace, namespace, filter_inactive=True)
        
        assert len(resources) == 1
        assert resources[0]['name'] == 'Test Resource'
    
    def test_parse_resources_empty_xml(self):
        """Тест парсинга пустого XML"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Resources>
    </Resources>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        resources = parse_resources(root, namespace, filter_inactive=True)
        assert len(resources) == 0
    
    def test_parse_resources_sample_xml(self, sample_xml_root, sample_namespace):
        """Тест парсинга из sample_project.xml"""
        resources = parse_resources(sample_xml_root, sample_namespace, filter_inactive=True)
        
        # В sample_project.xml должно быть 5 ресурсов
        assert len(resources) == 5
        
        # Проверяем структуру первого ресурса
        assert 'id' in resources[0]
        assert 'name' in resources[0]
        assert 'max_units' in resources[0]
        assert 'is_inactive' in resources[0]
        
        # Проверяем, что все ресурсы имеют уникальные ID
        ids = [r['id'] for r in resources]
        assert len(ids) == len(set(ids))
    
    def test_parse_resources_id_as_string(self, minimal_resource_xml):
        """Тест что ID всегда преобразуется в строку"""
        root, namespace = minimal_resource_xml
        resources = parse_resources(root, namespace, filter_inactive=True)
        
        assert isinstance(resources[0]['id'], str)
    
    def test_parse_resources_multiple_resources(self):
        """Тест парсинга множественных ресурсов"""
        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Resources>
        <Resource>
            <UID>1</UID>
            <Name>Resource 1</Name>
            <MaxUnits>1.0</MaxUnits>
        </Resource>
        <Resource>
            <UID>2</UID>
            <Name>Resource 2</Name>
            <MaxUnits>0.5</MaxUnits>
        </Resource>
        <Resource>
            <UID>3</UID>
            <Name>Resource 3</Name>
            <MaxUnits>2.0</MaxUnits>
        </Resource>
    </Resources>
</Project>'''
        root = etree.parse(io.BytesIO(xml_str.encode('utf-8'))).getroot()
        namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
        
        resources = parse_resources(root, namespace, filter_inactive=True)
        assert len(resources) == 3
        
        # Проверяем все ресурсы
        assert resources[0]['id'] == '1'
        assert resources[1]['id'] == '2'
        assert resources[2]['id'] == '3'
        
        assert resources[0]['max_units'] == '1.0'
        assert resources[1]['max_units'] == '0.5'
        assert resources[2]['max_units'] == '2.0'

