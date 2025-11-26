"""
Модуль управления персоналом
Содержит функции для работы с данными сотрудников и UI компонент для управления персоналом
"""
import streamlit as st
import json
import os
import sys


def get_base_path():
    """Определяет базовый путь для frozen и обычного режима"""
    if getattr(sys, 'frozen', False):
        # Если запущено через PyInstaller
        # Базовый путь - директория, где находится .exe
        if hasattr(sys, 'executable'):
            base_path = os.path.dirname(sys.executable)
        else:
            # Fallback
            base_path = os.path.dirname(os.path.abspath(__file__))
    else:
        # Если запущено напрямую через Python
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return base_path


# Определить базовый путь
BASE_PATH = get_base_path()


def load_employees_data():
    """Загрузка данных сотрудников и групп из JSON-файла"""
    try:
        # Получить актуальный путь (на случай изменения BASE_PATH)
        employees_file = os.path.join(BASE_PATH, "data", "employees.json")
        
        # Создать папку data/ если её нет
        data_dir = os.path.dirname(employees_file)
        os.makedirs(data_dir, exist_ok=True)
        
        # Если файл существует, загрузить данные
        if os.path.exists(employees_file):
            with open(employees_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'resources': data.get('resources', []),
                    'resource_groups': data.get('resource_groups', {})
                }
        else:
            # Создать файл с пустой структурой
            default_data = {
                'resources': [],
                'resource_groups': {}
            }
            with open(employees_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            return default_data
    except Exception as e:
        st.error(f"Ошибка при загрузке данных сотрудников: {str(e)}")
        return {'resources': [], 'resource_groups': {}}


def save_employees_data(resources, resource_groups):
    """Сохранение данных сотрудников и групп в JSON-файл"""
    try:
        # Получить актуальный путь (на случай изменения BASE_PATH)
        employees_file = os.path.join(BASE_PATH, "data", "employees.json")
        
        # Создать папку data/ если её нет
        data_dir = os.path.dirname(employees_file)
        os.makedirs(data_dir, exist_ok=True)
        
        data = {
            'resources': resources,
            'resource_groups': resource_groups
        }
        
        with open(employees_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Ошибка при сохранении данных сотрудников: {str(e)}")
        return False


def detect_conflicts(existing_resources, new_resources):
    """Обнаружение конфликтов между существующими и новыми сотрудниками (только по имени)"""
    # Конфликты по имени обрабатываются автоматически в merge_resources (пропускаются)
    # Эта функция возвращает пустой список, так как все конфликты по имени разрешаются автоматически
    return []


def merge_resources(existing_resources, new_resources, conflict_resolutions=None):
    """Объединение списков сотрудников с учетом решений по конфликтам (только по имени)"""
    if conflict_resolutions is None:
        conflict_resolutions = {}
    
    # Копируем существующих сотрудников
    merged = existing_resources.copy()
    
    # Словарь для быстрого поиска по имени
    existing_by_name = {r.get('name'): r for r in existing_resources}
    
    for new_resource in new_resources:
        new_name = new_resource.get('name', '')
        
        # Проверяем, есть ли конфликт по имени
        has_name_conflict = new_name in existing_by_name
        
        # Проверяем, есть ли решение для этого конфликта
        conflict_key = new_name
        resolution = conflict_resolutions.get(conflict_key)
        
        if resolution == 'skip':
            # Пропустить - не добавлять (оставить из файла)
            continue
        elif resolution == 'update':
            # Обновить существующего по имени
            if has_name_conflict:
                index = merged.index(existing_by_name[new_name])
                merged[index] = new_resource.copy()
        elif resolution == 'add_new':
            # Добавить как нового сотрудника
            merged.append(new_resource.copy())
        else:
            # По умолчанию: если имя совпадает, пропускаем (оставляем из файла)
            # Если имя не совпадает, добавляем новый ресурс
            if not has_name_conflict:
                merged.append(new_resource.copy())
    
    return merged


def render_personnel_management(workload_data):
    """
    UI компонент для управления персоналом
    
    Args:
        workload_data: список словарей с данными о рабочей нагрузке ресурсов
    """
    with st.expander("### 👥 Управление персоналом", expanded=True):
        # Инициализация applied_group если нужно
        if not hasattr(st.session_state, 'applied_group'):
            st.session_state.applied_group = None
        # Инициализация selected_resources_state для синхронизации выбора ресурсов
        if 'selected_resources_state' not in st.session_state:
            st.session_state.selected_resources_state = None
        # Инициализация счетчика для динамического ключа multiselect
        if 'multiselect_key_counter' not in st.session_state:
            st.session_state.multiselect_key_counter = 0
        
        # Инициализация переменных для использования вне табов
        selected_resources = []
        display_data = workload_data
        
        # Три таба: Текущий выбор, Управление группами и Управление сотрудниками
        tab1, tab2, tab3 = st.tabs(["🔍 Текущий выбор", "⚙️ Управление группами", "👤 Управление сотрудниками"])
        
        # ========== ТАБ 1: ТЕКУЩИЙ ВЫБОР ==========
        with tab1:
            # Выбор из сохраненных групп
            if st.session_state.resource_groups:
                st.markdown("**Выбрать из сохраненных групп:**")
                sorted_group_names = sorted(st.session_state.resource_groups.keys(), key=str.lower)
                group_names = ["-- Не выбрано --"] + sorted_group_names
                selected_group_tab1 = st.selectbox(
                    "Выберите группу:",
                    options=group_names,
                    key="selected_group_tab1_dropdown"
                )
                
                # Кнопка для применения группы
                if selected_group_tab1 != "-- Не выбрано --":
                    group_resources_tab1 = st.session_state.resource_groups[selected_group_tab1]
                    st.caption(f"👥 {len(group_resources_tab1)} человек: {', '.join(group_resources_tab1[:3])}{'...' if len(group_resources_tab1) > 3 else ''}")
                    
                    if st.button("✅ Применить группу", key="apply_group_tab1_btn"):
                        st.session_state.applied_group = (selected_group_tab1, group_resources_tab1)
                        # Обновить selected_resources_state списком ресурсов из группы
                        st.session_state.selected_resources_state = group_resources_tab1.copy()
                        # Увеличить счетчик для принудительного пересоздания multiselect
                        st.session_state.multiselect_key_counter += 1
                        st.success(f"✓ Группа '{selected_group_tab1}' применена ({len(group_resources_tab1)} чел.)")
                        st.rerun()
                    
                    st.markdown("---")
            
            all_names = sorted([item['resource_name'] for item in workload_data], key=str.lower)
            
            # Поиск по имени
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("Поиск по фамилии или имени:", placeholder="например, Иванов")
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                show_all = st.checkbox("Показать всех", value=True)
            
            # Фильтрация данных по поиску
            if show_all or not search_term:
                filtered_data = workload_data
            else:
                filtered_data = [item for item in workload_data 
                               if search_term.lower() in item['resource_name'].lower()]
            
            # Сортировка filtered_data по алфавиту
            filtered_data = sorted(filtered_data, key=lambda x: x['resource_name'].lower())
            
            # Получить список всех ресурсов из XML (не отфильтрованных поиском)
            # Использовать workload_data, чтобы всегда иметь все ресурсы из XML
            xml_resource_names = [item['resource_name'] for item in workload_data] if workload_data else []
            
            # Определить состав группы, если она применена
            group_resources_for_select = []
            if st.session_state.applied_group:
                group_name, group_resources = st.session_state.applied_group
                group_resources_for_select = group_resources.copy()
            
            # Объединить ресурсы из XML и группы для options в multiselect
            # Сначала ресурсы из группы (чтобы они были видны), затем из XML
            all_options = []
            # Добавить ресурсы из группы
            for name in group_resources_for_select:
                if name not in all_options:
                    all_options.append(name)
            # Добавить ресурсы из XML, которых еще нет
            for name in xml_resource_names:
                if name not in all_options:
                    all_options.append(name)
            # Сортировать по алфавиту
            all_options = sorted(all_options, key=str.lower)
            
            if not filtered_data and not group_resources_for_select:
                st.warning("Ресурсы, соответствующие вашему запросу, не найдены.")
                selected_resources = []
                display_data = []
            else:
                # Определить default значения для multiselect
                if st.session_state.applied_group:
                    # Группа применена: использовать selected_resources_state или ресурсы из группы
                    group_name, group_resources = st.session_state.applied_group
                    st.info(f"📌 Применена группа '{group_name}' ({len(group_resources)} чел.). Вы можете добавить дополнительные ресурсы из списка ниже.")
                    # Использовать selected_resources_state, если он установлен, иначе использовать ресурсы из группы
                    if st.session_state.selected_resources_state is not None:
                        default_resources = st.session_state.selected_resources_state.copy()
                    else:
                        default_resources = group_resources.copy()
                else:
                    # Группа не применена: использовать selected_resources_state или всех из filtered_data
                    if st.session_state.selected_resources_state is not None:
                        default_resources = st.session_state.selected_resources_state.copy()
                    else:
                        default_resources = xml_resource_names.copy()
                
                # Определить ресурсы, которых нет в XML (для подсветки)
                resources_not_in_xml = [name for name in all_options if name not in xml_resource_names]
                
                # Добавить CSS и JavaScript для подсветки ресурсов, которых нет в XML
                if resources_not_in_xml:
                    # Создать JSON-строку для JavaScript
                    resources_not_in_xml_json = json.dumps(resources_not_in_xml, ensure_ascii=False)
                    
                    highlight_css_js = f"""
                    <style>
                        /* Подсветка опций multiselect, которых нет в XML */
                        div[data-baseweb="select"] ul[role="listbox"] li {{
                            transition: background-color 0.2s;
                        }}
                        
                        /* Желтая подсветка для ресурсов, которых нет в XML */
                        div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"] {{
                            background-color: #FFF9C4 !important;
                            border-left: 3px solid #FBC02D !important;
                        }}
                        
                        div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"]:hover {{
                            background-color: #FFF59D !important;
                        }}
                        
                        /* Подсветка выбранных опций, которых нет в XML */
                        div[data-baseweb="select"] ul[role="listbox"] li[data-resource-not-in-xml="true"][aria-selected="true"] {{
                            background-color: #FFF176 !important;
                        }}
                        
                        /* Желтая подсветка для выбранных элементов (chips), которых нет в XML */
                        div[data-baseweb="select"] span[data-resource-not-in-xml="true"],
                        div[data-baseweb="select"] div[data-resource-not-in-xml="true"],
                        div[data-baseweb="select"] [data-resource-not-in-xml="true"] {{
                            background-color: #FFF9C4 !important;
                            color: #856404 !important;
                            border: 1px solid #FBC02D !important;
                            border-radius: 4px !important;
                            padding: 2px 6px !important;
                            margin: 2px !important;
                        }}
                        
                        /* Стили для выбранных значений в multiselect через data-baseweb */
                        div[data-baseweb="select"] [data-baseweb="tag"][data-resource-not-in-xml="true"],
                        div[data-baseweb="select"] [data-baseweb="multiValue"][data-resource-not-in-xml="true"] {{
                            background-color: #FFF9C4 !important;
                            color: #856404 !important;
                            border: 1px solid #FBC02D !important;
                        }}
                        
                        /* Универсальный селектор для всех элементов с атрибутом */
                        [data-resource-not-in-xml="true"] {{
                            background-color: #FFF9C4 !important;
                            color: #856404 !important;
                            border: 1px solid #FBC02D !important;
                        }}
                    </style>
                    <script>
                        (function() {{
                            const resourcesNotInXml = {resources_not_in_xml_json};
                            
                            function highlightResources() {{
                                // Найти все multiselect контейнеры
                                const selectContainers = document.querySelectorAll('div[data-baseweb="select"]');
                                
                                selectContainers.forEach(selectContainer => {{
                                    // Проверить, что это нужный multiselect (по label или key)
                                    const label = selectContainer.closest('.stMultiSelect') || 
                                                 selectContainer.closest('[data-testid*="stMultiSelect"]');
                                    
                                    if (!label) return;
                                    
                                    // Найти список опций
                                    const listbox = selectContainer.querySelector('ul[role="listbox"]');
                                    if (listbox) {{
                                        // Пройти по всем опциям
                                        const options = listbox.querySelectorAll('li[role="option"]');
                                        options.forEach(option => {{
                                            const optionText = option.textContent.trim();
                                            // Проверить, есть ли этот ресурс в списке тех, кого нет в XML
                                            if (resourcesNotInXml.some(resource => optionText === resource)) {{
                                                option.setAttribute('data-resource-not-in-xml', 'true');
                                            }} else {{
                                                option.removeAttribute('data-resource-not-in-xml');
                                            }}
                                        }});
                                    }}
                                    
                                    // Найти выбранные элементы (chips/tags)
                                    // В Streamlit multiselect выбранные значения находятся в разных местах
                                    // Попробуем найти их через различные селекторы
                                    
                                    // Метод 1: Найти через data-baseweb="tag" или data-baseweb="multiValue"
                                    const tags1 = selectContainer.querySelectorAll('[data-baseweb="tag"], [data-baseweb="multiValue"]');
                                    tags1.forEach(tag => {{
                                        const text = tag.textContent.trim();
                                        if (text && resourcesNotInXml.some(resource => text === resource)) {{
                                            tag.setAttribute('data-resource-not-in-xml', 'true');
                                            tag.style.setProperty('background-color', '#FFF9C4', 'important');
                                            tag.style.setProperty('color', '#856404', 'important');
                                            tag.style.setProperty('border', '1px solid #FBC02D', 'important');
                                        }}
                                    }});
                                    
                                    // Метод 2: Найти все span и div, которые не в dropdown
                                    const allElements = selectContainer.querySelectorAll('span, div');
                                    allElements.forEach(element => {{
                                        // Пропустить элементы внутри dropdown
                                        if (element.closest('ul[role="listbox"]')) {{
                                            return;
                                        }}
                                        
                                        // Пропустить элементы, которые уже обработаны
                                        if (element.closest('[data-baseweb="tag"]') || element.closest('[data-baseweb="multiValue"]')) {{
                                            return;
                                        }}
                                        
                                        const text = element.textContent.trim();
                                        // Проверить точное совпадение с ресурсами, которых нет в XML
                                        let matchingResource = null;
                                        for (let i = 0; i < resourcesNotInXml.length; i++) {{
                                            const resource = resourcesNotInXml[i];
                                            // Точное совпадение или совпадение с учетом пробелов
                                            if (text === resource || text.replace(/\\s+/g, ' ') === resource.replace(/\\s+/g, ' ')) {{
                                                matchingResource = resource;
                                                break;
                                            }}
                                        }}
                                        
                                        if (matchingResource) {{
                                            // Проверить, что это не пустой элемент и не часть структуры
                                            if (text.length > 0 && text.length < 200 && !element.querySelector('svg') && !element.querySelector('input')) {{
                                                // Проверить, что это не родительский элемент с множеством дочерних
                                                if (element.children.length < 3) {{
                                                    element.setAttribute('data-resource-not-in-xml', 'true');
                                                    // Применить стили с !important через setProperty
                                                    element.style.setProperty('background-color', '#FFF9C4', 'important');
                                                    element.style.setProperty('color', '#856404', 'important');
                                                    element.style.setProperty('border', '1px solid #FBC02D', 'important');
                                                    element.style.setProperty('border-radius', '4px', 'important');
                                                    element.style.setProperty('padding', '2px 6px', 'important');
                                                    element.style.setProperty('margin', '2px', 'important');
                                                    element.style.setProperty('display', 'inline-block', 'important');
                                                }}
                                            }}
                                        }} else if (element.hasAttribute('data-resource-not-in-xml')) {{
                                            // Убрать стили, если элемент больше не соответствует
                                            element.removeAttribute('data-resource-not-in-xml');
                                            element.style.removeProperty('background-color');
                                            element.style.removeProperty('color');
                                            element.style.removeProperty('border');
                                            element.style.removeProperty('border-radius');
                                            element.style.removeProperty('padding');
                                            element.style.removeProperty('margin');
                                            element.style.removeProperty('display');
                                        }}
                                    }});
                                }});
                            }}
                            
                            // Выполнить при загрузке
                            if (document.readyState === 'loading') {{
                                document.addEventListener('DOMContentLoaded', highlightResources);
                            }} else {{
                                highlightResources();
                            }}
                            
                            // Выполнить при изменении (для динамического обновления)
                            const observer = new MutationObserver(function(mutations) {{
                                let shouldHighlight = false;
                                mutations.forEach(function(mutation) {{
                                    if (mutation.addedNodes.length > 0 || mutation.type === 'childList') {{
                                        shouldHighlight = true;
                                    }}
                                }});
                                if (shouldHighlight) {{
                                    setTimeout(highlightResources, 50);
                                }}
                            }});
                            
                            observer.observe(document.body, {{
                                childList: true,
                                subtree: true
                            }});
                            
                            // Также выполнить после небольшой задержки для Streamlit
                            setTimeout(highlightResources, 100);
                            setTimeout(highlightResources, 300);
                            setTimeout(highlightResources, 500);
                            setTimeout(highlightResources, 1000);
                            setTimeout(highlightResources, 2000);
                            
                            // Выполнить при клике (для обновления при открытии dropdown)
                            document.addEventListener('click', function() {{
                                setTimeout(highlightResources, 100);
                            }});
                            
                            // Выполнить при изменении значения (для обновления выбранных элементов)
                            function setupInputObserver() {{
                                const selectContainers = document.querySelectorAll('div[data-baseweb="select"]');
                                selectContainers.forEach(container => {{
                                    const inputObserver = new MutationObserver(function(mutations) {{
                                        let shouldUpdate = false;
                                        mutations.forEach(function(mutation) {{
                                            if (mutation.type === 'childList' || mutation.type === 'attributes') {{
                                                shouldUpdate = true;
                                            }}
                                        }});
                                        if (shouldUpdate) {{
                                            setTimeout(highlightResources, 50);
                                        }}
                                    }});
                                    
                                    inputObserver.observe(container, {{
                                        childList: true,
                                        subtree: true,
                                        attributes: true,
                                        attributeFilter: ['class', 'style']
                                    }});
                                }});
                            }}
                            
                            // Настроить observer после небольшой задержки
                            setTimeout(setupInputObserver, 200);
                            setTimeout(setupInputObserver, 1000);
                        }})();
                    </script>
                    """
                    st.markdown(highlight_css_js, unsafe_allow_html=True)
                
                # Множественный выбор - options содержат ресурсы из группы + ресурсы из XML
                # Использовать динамический ключ для принудительного пересоздания виджета при применении группы
                multiselect_key = f"current_selection_multiselect_{st.session_state.multiselect_key_counter}"
                selected_resources = st.multiselect(
                    "Выберите конкретные ресурсы для анализа:",
                    options=all_options,
                    default=default_resources,
                    key=multiselect_key
                )
                
                # Синхронизировать изменения в multiselect с selected_resources_state
                current_state = st.session_state.selected_resources_state
                if current_state is None or selected_resources != current_state:
                    st.session_state.selected_resources_state = selected_resources.copy()
                
                # НОВАЯ ФУНКЦИЯ: Быстрое сохранение текущего выбора как группы
                if selected_resources and len(selected_resources) > 0:
                    st.markdown("---")
                    with st.expander("💾 Сохранить текущий выбор как группу"):
                        # Инициализация состояния диалога
                        if 'group_save_dialog' not in st.session_state:
                            st.session_state.group_save_dialog = None
                        if 'group_save_new_name' not in st.session_state:
                            st.session_state.group_save_new_name = ""
                        
                        quick_group_name = st.text_input(
                            "Название новой группы:",
                            placeholder="например, Команда А",
                            key="quick_save_group_name"
                        )
                        
                        # Если диалог активен для этой группы, показать диалог выбора
                        if st.session_state.group_save_dialog == quick_group_name and quick_group_name:
                            st.warning(f"Группа '{quick_group_name}' уже существует. Выберите действие:")
                            
                            save_action = st.radio(
                                "Что вы хотите сделать?",
                                ["Перезаписать группу", "Создать новую группу", "Отменить"],
                                key="group_save_action_radio"
                            )
                            
                            # Если выбрано "Создать новую группу", показать поле для нового имени
                            if save_action == "Создать новую группу":
                                st.session_state.group_save_new_name = st.text_input(
                                    "Введите название новой группы:",
                                    value=st.session_state.group_save_new_name,
                                    placeholder="например, Команда А (копия)",
                                    key="group_save_new_name_input"
                                )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ Подтвердить", key="confirm_save_btn"):
                                    if save_action == "Перезаписать группу":
                                        # Перезаписать группу с новым составом
                                        st.session_state.resource_groups[quick_group_name] = selected_resources.copy()
                                        # Обновить примененную группу, если она была изменена
                                        if st.session_state.applied_group and st.session_state.applied_group[0] == quick_group_name:
                                            st.session_state.applied_group = (quick_group_name, selected_resources.copy())
                                            # Обновить selected_resources_state списком ресурсов из перезаписанной группы
                                            st.session_state.selected_resources_state = selected_resources.copy()
                                        # Сохранить в файл
                                        save_employees_data(
                                            st.session_state.saved_resources,
                                            st.session_state.resource_groups
                                        )
                                        st.success(f"✓ Группа '{quick_group_name}' перезаписана ({len(selected_resources)} чел.)")
                                        st.session_state.group_save_dialog = None
                                        st.session_state.group_save_new_name = ""
                                        st.rerun()
                                    elif save_action == "Создать новую группу":
                                        # Создать новую группу с новым именем
                                        new_name = st.session_state.group_save_new_name
                                        if not new_name:
                                            st.error("Введите название новой группы")
                                        elif new_name in st.session_state.resource_groups:
                                            st.error("Группа с таким названием уже существует")
                                        else:
                                            st.session_state.resource_groups[new_name] = selected_resources.copy()
                                            # Сохранить в файл
                                            save_employees_data(
                                                st.session_state.saved_resources,
                                                st.session_state.resource_groups
                                            )
                                            st.success(f"✓ Группа '{new_name}' создана ({len(selected_resources)} чел.)")
                                            st.session_state.group_save_dialog = None
                                            st.session_state.group_save_new_name = ""
                                            st.rerun()
                                    else:  # Отменить
                                        st.session_state.group_save_dialog = None
                                        st.session_state.group_save_new_name = ""
                                        st.rerun()
                            with col2:
                                if st.button("❌ Отменить", key="cancel_save_btn"):
                                    st.session_state.group_save_dialog = None
                                    st.session_state.group_save_new_name = ""
                                    st.rerun()
                        else:
                            # Кнопка сохранения (показывается только когда диалог не активен)
                            if st.button("💾 Сохранить", key="quick_save_btn"):
                                if not quick_group_name:
                                    st.error("Введите название группы")
                                elif quick_group_name in st.session_state.resource_groups:
                                    # Активировать диалог выбора
                                    st.session_state.group_save_dialog = quick_group_name
                                    st.rerun()
                                else:
                                    # Группа не существует, создать новую
                                    st.session_state.resource_groups[quick_group_name] = selected_resources.copy()
                                    # Сохранить в файл
                                    save_employees_data(
                                        st.session_state.saved_resources,
                                        st.session_state.resource_groups
                                    )
                                    st.success(f"✓ Группа '{quick_group_name}' создана ({len(selected_resources)} чел.)")
                                    st.rerun()
                
                if selected_resources:
                    # Использовать workload_data вместо filtered_data для отображения всех выбранных ресурсов
                    # Это позволяет показывать ресурсы из группы, даже если они не проходят фильтр поиска
                    display_data = [item for item in workload_data 
                                  if item['resource_name'] in selected_resources]
                else:
                    display_data = workload_data
        
        # ========== ТАБ 2: УПРАВЛЕНИЕ ГРУППАМИ ==========
        with tab2:
            # Выбор и применение сохраненной группы
            if st.session_state.resource_groups:
                st.markdown("**Применить сохраненную группу:**")
                sorted_group_names = sorted(st.session_state.resource_groups.keys(), key=str.lower)
                group_names = ["-- Не выбрано --"] + sorted_group_names
                selected_group = st.selectbox(
                    "Выберите группу:",
                    options=group_names,
                    key="selected_group_dropdown"
                )
                
                # Кнопка для применения группы
                if selected_group != "-- Не выбрано --":
                    group_resources = st.session_state.resource_groups[selected_group]
                    st.caption(f"👥 {len(group_resources)} человек: {', '.join(group_resources[:3])}{'...' if len(group_resources) > 3 else ''}")
                    
                    if st.button("✅ Применить группу", key="apply_group_btn"):
                        st.session_state.applied_group = (selected_group, group_resources)
                        # Обновить selected_resources_state списком ресурсов из группы
                        st.session_state.selected_resources_state = group_resources.copy()
                        # Увеличить счетчик для принудительного пересоздания multiselect
                        st.session_state.multiselect_key_counter += 1
                        st.success(f"✓ Группа '{selected_group}' применена ({len(group_resources)} чел.)")
                        st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("У вас пока нет сохраненных групп. Создайте новую ниже.")
            
            # Создание новой группы с нуля
            st.markdown("**Создать новую группу:**")
            with st.expander("➕ Создать группу", expanded=not st.session_state.resource_groups):
                new_group_name = st.text_input("Название группы:", placeholder="например, Разработчики", key="new_group_name_input")
                
                # Использовать полный список сохраненных сотрудников
                all_names = sorted([r.get('name', '') for r in st.session_state.saved_resources], key=str.lower)
                new_group_resources = st.multiselect(
                    "Выберите участников группы:",
                    options=all_names,
                    key="new_group_resources"
                )
                
                if st.button("💾 Сохранить группу", key="save_new_group_btn"):
                    if not new_group_name:
                        st.error("Введите название группы")
                    elif not new_group_resources:
                        st.error("Выберите хотя бы одного участника")
                    elif new_group_name in st.session_state.resource_groups:
                        st.error("Группа с таким названием уже существует")
                    else:
                        st.session_state.resource_groups[new_group_name] = new_group_resources
                        # Сохранить в файл
                        save_employees_data(
                            st.session_state.saved_resources,
                            st.session_state.resource_groups
                        )
                        st.success(f"✓ Группа '{new_group_name}' создана ({len(new_group_resources)} чел.)")
                        st.rerun()
            
            # Управление существующими группами
            if st.session_state.resource_groups:
                st.markdown("---")
                st.markdown("**Управление группами:**")
                for group_name in list(st.session_state.resource_groups.keys()):
                    group_members = st.session_state.resource_groups[group_name]
                    
                    # Заголовок группы с кнопкой удаления
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{group_name}** ({len(group_members)} чел.)")
                    with col2:
                        if st.button("🗑️", key=f"delete_{group_name}", help=f"Удалить группу '{group_name}'"):
                            del st.session_state.resource_groups[group_name]
                            if st.session_state.applied_group and st.session_state.applied_group[0] == group_name:
                                st.session_state.applied_group = None
                                # Сбросить selected_resources_state при удалении примененной группы
                                st.session_state.selected_resources_state = None
                            # Сохранить в файл
                            save_employees_data(
                                st.session_state.saved_resources,
                                st.session_state.resource_groups
                            )
                            st.success(f"✓ Группа '{group_name}' удалена")
                            st.rerun()
                    
                    # Expander для редактирования состава группы
                    with st.expander(f"✏️ Редактировать группу '{group_name}'"):
                        # Использовать полный список сохраненных сотрудников
                        all_names = sorted([r.get('name', '') for r in st.session_state.saved_resources], key=str.lower)
                        edited_group_resources = st.multiselect(
                            "Выберите участников группы:",
                            options=all_names,
                            default=group_members,
                            key=f"edit_group_{group_name}"
                        )
                        
                        if st.button("💾 Сохранить изменения", key=f"save_edit_{group_name}"):
                            st.session_state.resource_groups[group_name] = edited_group_resources.copy()
                            # Обновить примененную группу, если она была изменена
                            if st.session_state.applied_group and st.session_state.applied_group[0] == group_name:
                                st.session_state.applied_group = (group_name, edited_group_resources.copy())
                                # Обновить selected_resources_state списком ресурсов из обновленной группы
                                st.session_state.selected_resources_state = edited_group_resources.copy()
                            # Сохранить в файл
                            save_employees_data(
                                st.session_state.saved_resources,
                                st.session_state.resource_groups
                            )
                            st.success(f"✓ Группа '{group_name}' обновлена ({len(edited_group_resources)} чел.)")
                            st.rerun()
                    
                    st.markdown("")  # Добавить отступ между группами
        
        # ========== ТАБ 3: УПРАВЛЕНИЕ СОТРУДНИКАМИ ==========
        with tab3:
            st.markdown("**Управление перечнем сотрудников:**")
            
            # Отображение списка сотрудников
            if st.session_state.saved_resources:
                st.markdown(f"**Всего сотрудников: {len(st.session_state.saved_resources)}**")
                
                # Инициализация состояния для редактирования
                if 'editing_employee' not in st.session_state:
                    st.session_state.editing_employee = None
                
                # Обработка удаления
                if 'delete_employee_name' in st.session_state and st.session_state.delete_employee_name:
                    employee_name_to_delete = st.session_state.delete_employee_name
                    st.session_state.saved_resources = [
                        r for r in st.session_state.saved_resources 
                        if r.get('name') != employee_name_to_delete
                    ]
                    # Обновить группы - удалить сотрудника из всех групп
                    for group_name in st.session_state.resource_groups:
                        st.session_state.resource_groups[group_name] = [
                            name for name in st.session_state.resource_groups[group_name]
                            if name != employee_name_to_delete
                        ]
                    # Сохранить в файл
                    save_employees_data(
                        st.session_state.saved_resources,
                        st.session_state.resource_groups
                    )
                    st.success(f"✓ Сотрудник '{employee_name_to_delete}' удален")
                    st.session_state.delete_employee_name = None
                    st.session_state.editing_employee = None
                    st.rerun()
                
                # Инициализация состояния для фильтров и сортировки
                if 'filter_name' not in st.session_state:
                    st.session_state.filter_name = ''
                if 'filter_max_units' not in st.session_state:
                    st.session_state.filter_max_units = ''
                if 'sort_column' not in st.session_state:
                    st.session_state.sort_column = 'Имя'
                if 'sort_direction' not in st.session_state:
                    st.session_state.sort_direction = 'По возрастанию'
                
                # Секция фильтров и сортировки
                st.markdown("---")
                st.markdown("**Фильтры и сортировка:**")
                
                # Фильтры
                filter_col1, filter_col2 = st.columns(2)
                with filter_col1:
                    filter_name = st.text_input("Фильтр по имени:", value=st.session_state.filter_name, key="filter_name_input", placeholder="Введите имя...")
                    st.session_state.filter_name = filter_name
                with filter_col2:
                    filter_max_units = st.text_input("Фильтр по Max Units:", value=st.session_state.filter_max_units, key="filter_max_units_input", placeholder="Введите значение...")
                    st.session_state.filter_max_units = filter_max_units
                
                # Сортировка
                sort_col1, sort_col2 = st.columns(2)
                with sort_col1:
                    sort_column = st.selectbox(
                        "Сортировать по:",
                        options=['Имя', 'Max Units'],
                        index=['Имя', 'Max Units'].index(st.session_state.sort_column) if st.session_state.sort_column in ['Имя', 'Max Units'] else 0,
                        key="sort_column_select"
                    )
                    st.session_state.sort_column = sort_column
                with sort_col2:
                    sort_direction = st.radio(
                        "Направление сортировки:",
                        options=['По возрастанию', 'По убыванию'],
                        index=0 if st.session_state.sort_direction == 'По возрастанию' else 1,
                        key="sort_direction_radio",
                        horizontal=True
                    )
                    st.session_state.sort_direction = sort_direction
                
                # Применение фильтров
                filtered_resources = st.session_state.saved_resources.copy()
                
                if st.session_state.filter_name:
                    filtered_resources = [
                        r for r in filtered_resources 
                        if st.session_state.filter_name.lower() in str(r.get('name', '')).lower()
                    ]
                
                if st.session_state.filter_max_units:
                    filtered_resources = [
                        r for r in filtered_resources 
                        if st.session_state.filter_max_units.lower() in str(r.get('max_units', '')).lower()
                    ]
                
                # Применение сортировки
                sort_reverse = st.session_state.sort_direction == 'По убыванию'
                
                if st.session_state.sort_column == 'Имя':
                    sorted_resources = sorted(
                        filtered_resources,
                        key=lambda x: str(x.get('name', '')).lower(),
                        reverse=sort_reverse
                    )
                elif st.session_state.sort_column == 'Max Units':
                    sorted_resources = sorted(
                        filtered_resources,
                        key=lambda x: float(str(x.get('max_units', '0')).replace(',', '.')) if str(x.get('max_units', '0')).replace(',', '.').replace('.', '').isdigit() else 0,
                        reverse=sort_reverse
                    )
                else:
                    sorted_resources = filtered_resources
                
                # Показать количество отфильтрованных записей
                if len(filtered_resources) != len(st.session_state.saved_resources):
                    st.info(f"Показано {len(filtered_resources)} из {len(st.session_state.saved_resources)} сотрудников")
                
                # CSS стили для таблицы сотрудников
                st.markdown("""
                <style>
                /* Уменьшение высоты кнопок до высоты текста в таблице сотрудников */
                button[kind="secondary"] {
                    height: auto !important;
                    min-height: 1.5em !important;
                    padding: 0.25em 0.5em !important;
                    line-height: 1.2 !important;
                }
                
                /* Уменьшение межстрочного интервала в таблице */
                div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
                    margin-bottom: 2px !important;
                    padding-bottom: 2px !important;
                }
                
                /* Уменьшение отступов в контейнерах строк таблицы */
                div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div {
                    margin-bottom: 2px !important;
                }
                
                /* Уменьшение отступов между колонками в строках */
                div[data-testid="column"] {
                    margin-bottom: 2px !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # JavaScript для применения стилей прокрутки к таблице
                st.markdown("""
                <script>
                setTimeout(function() {
                    // Найти контейнер с заголовками таблицы
                    const headers = Array.from(document.querySelectorAll('*')).find(el => 
                        el.textContent && el.textContent.includes('Имя') && 
                        el.textContent.includes('Max Units')
                    );
                    if (headers) {
                        // Найти родительский контейнер Streamlit
                        let container = headers.closest('[data-testid="stVerticalBlock"]');
                        if (!container) {
                            container = headers.closest('div[class*="block-container"]');
                        }
                        if (container) {
                            container.style.maxHeight = '400px';
                            container.style.overflowY = 'auto';
                            container.style.overflowX = 'auto';
                            container.style.border = '1px solid #e0e0e0';
                            container.style.borderRadius = '4px';
                            container.style.padding = '10px';
                        }
                        
                        // Применить стили к кнопкам в таблице
                        const buttons = container.querySelectorAll('button[kind="secondary"]');
                        buttons.forEach(button => {
                            button.style.height = 'auto';
                            button.style.minHeight = '1.5em';
                            button.style.padding = '0.25em 0.5em';
                            button.style.lineHeight = '1.2';
                        });
                        
                        // Уменьшить межстрочный интервал между строками таблицы
                        const verticalBlocks = container.querySelectorAll('[data-testid="stVerticalBlock"]');
                        verticalBlocks.forEach((block, index) => {
                            // Пропустить первый блок (заголовки) и применить к остальным
                            if (index > 0) {
                                block.style.marginBottom = '2px';
                                block.style.paddingBottom = '2px';
                                
                                // Также уменьшить отступы внутри блока
                                const innerDivs = block.querySelectorAll('div[data-testid="stVerticalBlock"]');
                                innerDivs.forEach(innerDiv => {
                                    innerDiv.style.marginBottom = '2px';
                                    innerDiv.style.paddingBottom = '2px';
                                });
                                
                                // Уменьшить отступы в колонках
                                const columns = block.querySelectorAll('[data-testid="column"]');
                                columns.forEach(column => {
                                    column.style.marginBottom = '2px';
                                });
                            }
                        });
                    }
                }, 200);
                </script>
                """, unsafe_allow_html=True)
                
                # Заголовки таблицы
                st.markdown("---")
                header_col1, header_col2, header_col3, header_col4 = st.columns([3, 2, 1, 1])
                with header_col1:
                    st.markdown("**Имя**")
                with header_col2:
                    st.markdown("**Max Units**")
                with header_col3:
                    st.markdown("**Действия**")
                with header_col4:
                    st.markdown("")
                
                # Отображение списка сотрудников с кнопками
                for idx, employee in enumerate(sorted_resources):
                    employee_name = employee.get('name', '')
                    employee_max_units = employee.get('max_units', '1.0')
                    
                    # Если этот сотрудник редактируется
                    if st.session_state.editing_employee == employee_name:
                        with st.container():
                            st.markdown("---")
                            st.markdown(f"**✏️ Редактирование: {employee_name}**")
                            
                            col1, col2, col3 = st.columns([2, 2, 1])
                            with col1:
                                edited_name = st.text_input("Имя:", value=employee_name, key=f"edit_name_{idx}")
                            with col2:
                                edited_max_units = st.text_input("Max Units:", value=employee_max_units, key=f"edit_max_units_{idx}")
                            with col3:
                                st.markdown("<br>", unsafe_allow_html=True)  # Отступ для выравнивания
                                save_col, cancel_col = st.columns(2)
                                with save_col:
                                    if st.button("💾", key=f"save_{idx}", help="Сохранить"):
                                        # Проверить на дубликаты (кроме текущего)
                                        existing_names = [r.get('name') for r in st.session_state.saved_resources if r.get('name') != employee_name]
                                        
                                        if edited_name in existing_names:
                                            st.error(f"Сотрудник с именем '{edited_name}' уже существует")
                                        else:
                                            # Обновить данные сотрудника
                                            old_name = employee['name']
                                            employee['name'] = edited_name
                                            employee['max_units'] = edited_max_units
                                            
                                            # Обновить имя в группах, если оно изменилось
                                            if edited_name != old_name:
                                                for group_name in st.session_state.resource_groups:
                                                    if old_name in st.session_state.resource_groups[group_name]:
                                                        index = st.session_state.resource_groups[group_name].index(old_name)
                                                        st.session_state.resource_groups[group_name][index] = edited_name
                                            
                                            # Сохранить в файл
                                            save_employees_data(
                                                st.session_state.saved_resources,
                                                st.session_state.resource_groups
                                            )
                                            st.session_state.editing_employee = None
                                            st.success(f"✓ Сотрудник '{edited_name}' обновлен")
                                            st.rerun()
                                with cancel_col:
                                    if st.button("❌", key=f"cancel_{idx}", help="Отменить"):
                                        st.session_state.editing_employee = None
                                        st.rerun()
                    else:
                        # Обычное отображение строки сотрудника
                        with st.container():
                            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                            with col1:
                                st.text(employee_name)
                            with col2:
                                st.text(employee_max_units)
                            with col3:
                                if st.button("✏️", key=f"edit_{idx}", help="Редактировать"):
                                    st.session_state.editing_employee = employee_name
                                    st.rerun()
                            with col4:
                                if st.button("🗑️", key=f"delete_{idx}", help="Удалить"):
                                    st.session_state.delete_employee_name = employee_name
                                    st.rerun()
            else:
                st.info("Список сотрудников пуст. Добавьте сотрудников через форму ниже или загрузите XML-файл проекта.")
            
            # Добавление нового сотрудника
            st.markdown("---")
            st.markdown("**Добавить нового сотрудника:**")
            with st.expander("➕ Добавить сотрудника", expanded=not st.session_state.saved_resources):
                new_employee_name = st.text_input("Имя сотрудника:", key="new_employee_name")
                new_employee_max_units = st.text_input("Max Units:", value="1.0", key="new_employee_max_units")
                
                if st.button("💾 Добавить сотрудника", key="add_employee_btn"):
                    if not new_employee_name:
                        st.error("Введите имя сотрудника")
                    else:
                        # Проверить на дубликаты по имени
                        existing_names = [r.get('name') for r in st.session_state.saved_resources]
                        
                        if new_employee_name in existing_names:
                            st.error(f"Сотрудник с именем '{new_employee_name}' уже существует")
                        else:
                            new_employee = {
                                'name': new_employee_name,
                                'max_units': new_employee_max_units or '1.0'
                            }
                            st.session_state.saved_resources.append(new_employee)
                            # Сохранить в файл
                            save_employees_data(
                                st.session_state.saved_resources,
                                st.session_state.resource_groups
                            )
                            st.success(f"✓ Сотрудник '{new_employee_name}' добавлен")
                            st.rerun()
    
    # Возвращаем выбранные ресурсы и данные для отображения
    return selected_resources, display_data

