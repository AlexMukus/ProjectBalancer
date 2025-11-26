"""
Модуль для построения диаграммы Ганта (суммарный план график)
"""
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict
from msproject_utils import parse_date, find_task_by_name_and_dates


def create_gantt_chart(parser, selected_resources=None, resource_groups=None, date_range_start=None, date_range_end=None, parser_to_file_name=None, workload_data=None):
    """
    Создает диаграмму Ганта для задач выбранных ресурсов и групп
    
    Args:
        parser: MSProjectParser или MultiProjectParser с данными о задачах, ресурсах и назначениях
        selected_resources: список имен выбранных ресурсов (опционально)
        resource_groups: словарь групп ресурсов {group_name: [resource_names]} (опционально)
        date_range_start: начало временного диапазона анализа (datetime.date или None)
        date_range_end: конец временного диапазона анализа (datetime.date или None)
        parser_to_file_name: словарь {parser: file_name} для маппинга парсеров к именам файлов (опционально)
        workload_data: список словарей с данными о рабочей нагрузке (опционально). Если передан, используется вместо повторного прохода по parser
    
    Returns:
        Plotly figure с диаграммой Ганта или None если нет данных
    """
    # Определить список ресурсов для отображения
    resources_to_show = set()
    
    if selected_resources:
        resources_to_show.update(selected_resources)
    
    if resource_groups:
        for group_resources in resource_groups.values():
            resources_to_show.update(group_resources)
    
    # Если нет выбранных ресурсов и групп, вернуть None
    if not resources_to_show:
        return None
    
    # Получить маппинг resource_id -> resource_name
    resource_id_to_name = {}
    if hasattr(parser, 'get_resource_id_mapping'):
        # Для MultiProjectParser
        resource_id_to_name = parser.get_resource_id_mapping()
    else:
        # Для MSProjectParser
        for resource in parser.resources:
            resource_id = resource.get('id', '')
            resource_name = resource.get('name', '')
            if resource_id and resource_name:
                resource_id_to_name[resource_id] = resource_name
    
    # Получить маппинг (task_name, task_start, task_finish) -> project_name (используя имена файлов)
    task_key_to_project = {}
    if hasattr(parser, 'parsers'):
        # MultiProjectParser - получить project_name из имени файла для каждого парсера
        for sub_parser in parser.parsers:
            # Использовать имя файла как имя проекта
            if parser_to_file_name and sub_parser in parser_to_file_name:
                project_name = parser_to_file_name[sub_parser]
            else:
                # Fallback: использовать project_name из парсера или имя по умолчанию
                project_name = getattr(sub_parser, 'project_name', 'Неизвестный проект')
            for task in sub_parser.tasks:
                task_name = task.get('name', '')
                task_start = task.get('start', '')
                task_finish = task.get('finish', '')
                if task_name:
                    task_key = (task_name, task_start, task_finish)
                    task_key_to_project[task_key] = project_name
    else:
        # MSProjectParser - использовать имя файла как имя проекта
        if parser_to_file_name and parser in parser_to_file_name:
            project_name = parser_to_file_name[parser]
        else:
            # Fallback: использовать project_name из парсера или имя по умолчанию
            project_name = getattr(parser, 'project_name', 'Неизвестный проект')
        for task in parser.tasks:
            task_name = task.get('name', '')
            task_start = task.get('start', '')
            task_finish = task.get('finish', '')
            if task_name:
                task_key = (task_name, task_start, task_finish)
                task_key_to_project[task_key] = project_name
    
    # Собрать все задачи с назначенными ресурсами
    # Используем workload_data, если он передан, иначе используем текущую логику
    tasks_data = []
    
    if workload_data:
        # Использовать данные из workload_data (уже вычисленные)
        for item in workload_data:
            resource_name = item.get('resource_name', '')
            
            # Фильтровать по выбранным ресурсам
            if resource_name not in resources_to_show:
                continue
            
            # Получить задачи для ресурса
            tasks = item.get('tasks', [])
            
            for task_detail in tasks:
                task_id = task_detail.get('task_id', 'N/A')  # Только для отладки
                task_name = task_detail.get('task_name', 'Без названия')
                start_str = task_detail.get('start', '')
                finish_str = task_detail.get('finish', '')
                
                if not start_str or not finish_str or start_str == 'N/A' or finish_str == 'N/A':
                    continue
                
                # Парсить даты
                start_date = _parse_date(parser, start_str)
                finish_date = _parse_date(parser, finish_str)
                
                if not start_date or not finish_date:
                    continue
                
                # Получить название проекта из маппинга
                task_key = (task_name, start_str, finish_str)
                project_name = task_key_to_project.get(task_key, 'Неизвестный проект')
                
                # Добавить задачу
                tasks_data.append({
                    'resource_name': resource_name,
                    'project_name': project_name,
                    'task_name': task_name,
                    'start': start_date,
                    'finish': finish_date,
                    'task_id': task_id  # Только для отладки
                })
    else:
        # Использовать текущую логику (обратная совместимость)
        # Получить список ресурсов для обработки
        if hasattr(parser, 'parsers'):
            # MultiProjectParser - получить объединенные ресурсы
            resources_to_process = parser.resources
        else:
            # MSProjectParser
            resources_to_process = parser.resources
        
        # Проходим по ресурсам (как в разделе "Детализация задач")
        for resource in resources_to_process:
            resource_name = resource.get('name', '')
            
            # Фильтровать по выбранным ресурсам
            if resource_name not in resources_to_show:
                continue
            
            # Получить assignments для ресурса (как в разделе "Детализация задач")
            if hasattr(parser, 'get_assignments_for_resource'):
                # MultiProjectParser - использовать специальный метод
                resource_assignments = parser.get_assignments_for_resource(resource_name)
            else:
                # MSProjectParser - использовать resource_name (парсим только по имени)
                resource_assignments = [a for a in parser.assignments if a.get('resource_name') == resource_name]
            
            # Обработать каждое назначение
            for assignment in resource_assignments:
                # Поиск задачи по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    parser.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                if not task:
                    continue
                
                # Получить даты начала и окончания
                start_str = task.get('start', '')
                finish_str = task.get('finish', '')
                
                if not start_str or not finish_str:
                    continue
                
                # Парсить даты
                start_date = _parse_date(parser, start_str)
                finish_date = _parse_date(parser, finish_str)
                
                if not start_date or not finish_date:
                    continue
                
                # Получить название проекта из маппинга
                task_name = task.get('name', 'Без названия')
                task_key = (task_name, start_str, finish_str)
                project_name = task_key_to_project.get(task_key, 'Неизвестный проект')
                
                # Добавить задачу
                tasks_data.append({
                    'resource_name': resource_name,
                    'project_name': project_name,
                    'task_name': task_name,
                    'start': start_date,
                    'finish': finish_date,
                    'task_id': task.get('id', 'N/A')  # Только для отладки
                })
    
    # Если нет задач, вернуть None
    if not tasks_data:
        return None
    
    # Группировать задачи по ресурсам
    tasks_by_resource = defaultdict(list)
    for task_data in tasks_data:
        resource_name = task_data['resource_name']
        tasks_by_resource[resource_name].append(task_data)
    
    # Сортировать ресурсы по имени
    sorted_resources = sorted(tasks_by_resource.keys())
    
    # Подготовить данные для Plotly
    y_positions = []
    y_labels = []
    x_starts = []
    x_ends = []
    colors = []
    hover_texts = []
    
    # Цвета для разных ресурсов
    import plotly.colors as pc
    resource_colors = {}
    color_palette = pc.qualitative.Set3 + pc.qualitative.Pastel + pc.qualitative.Dark2
    
    y_pos = 0
    for resource_name in sorted_resources:
        resource_tasks = tasks_by_resource[resource_name]
        # Сортировать задачи по дате начала
        resource_tasks.sort(key=lambda x: x['start'])
        
        # Получить цвет для ресурса
        if resource_name not in resource_colors:
            resource_colors[resource_name] = color_palette[len(resource_colors) % len(color_palette)]
        
        color = resource_colors[resource_name]
        
        for task_data in resource_tasks:
            y_positions.append(y_pos)
            # Упрощенная метка: только имя ресурса
            y_labels.append(task_data['resource_name'])
            x_starts.append(task_data['start'])
            x_ends.append(task_data['finish'])
            colors.append(color)
            hover_texts.append(
                f"Ресурс: {task_data['resource_name']}<br>"
                f"Проект: {task_data['project_name']}<br>"
                f"Задача: {task_data['task_name']}<br>"
                f"Начало: {task_data['start'].strftime('%d.%m.%Y %H:%M')}<br>"
                f"Окончание: {task_data['finish'].strftime('%d.%m.%Y %H:%M')}"
            )
            y_pos += 1
    
    # Создать фигуру
    fig = go.Figure()
    
    # Добавить горизонтальные линии для каждой задачи
    for i in range(len(y_positions)):
        fig.add_trace(go.Scatter(
            x=[x_starts[i], x_ends[i]],
            y=[y_positions[i], y_positions[i]],
            mode='lines+markers',
            line=dict(color=colors[i], width=16),  # Увеличена толщина в 2 раза
            marker=dict(size=16),  # Увеличен размер маркеров пропорционально
            name=y_labels[i],
            showlegend=False,
            hovertemplate=hover_texts[i] + '<extra></extra>',
            hoverlabel=dict(bgcolor=colors[i], font_size=12)
        ))
    
    # Определить диапазон Y для вертикальных линий
    y_min = min(y_positions) if y_positions else 0
    y_max = max(y_positions) if y_positions else 0
    
    # Добавить вертикальную линию текущей даты (красный пунктир)
    current_date = datetime.now()
    if y_positions:
        fig.add_shape(
            type="line",
            x0=current_date,
            x1=current_date,
            y0=y_min - 0.5,
            y1=y_max + 0.5,
            line=dict(color="red", width=2, dash="dash"),
            layer="above"
        )
        # Добавить аннотацию для текущей даты
        fig.add_annotation(
            x=current_date,
            y=y_max + 0.5,
            text="Сегодня",
            showarrow=True,
            arrowhead=2,
            arrowcolor="red",
            bgcolor="white",
            bordercolor="red",
            borderwidth=1,
            font=dict(color="red", size=10)
        )
    
    # Добавить вертикальные линии начала и конца временного диапазона анализа (светлосиний)
    if date_range_start and date_range_end:
        # Конвертировать date в datetime
        from datetime import datetime as dt_class
        range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
        range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        
        if y_positions:
            # Линия начала диапазона
            fig.add_shape(
                type="line",
                x0=range_start_dt,
                x1=range_start_dt,
                y0=y_min - 0.5,
                y1=y_max + 0.5,
                line=dict(color="lightblue", width=2),
                layer="above"
            )
            # Линия конца диапазона
            fig.add_shape(
                type="line",
                x0=range_end_dt,
                x1=range_end_dt,
                y0=y_min - 0.5,
                y1=y_max + 0.5,
                line=dict(color="lightblue", width=2),
                layer="above"
            )
    
    # Определить диапазон отображения для оси X
    xaxis_range = None
    if date_range_start and date_range_end:
        # Конвертировать date в datetime
        from datetime import datetime as dt_class
        range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
        range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        
        # Слева: начало временного диапазона анализа - 7 дней
        # Справа: конец временного диапазона анализа + 14 дней
        xaxis_range_start = range_start_dt - timedelta(days=7)
        xaxis_range_end = range_end_dt + timedelta(days=14)
        xaxis_range = [xaxis_range_start, xaxis_range_end]
    elif tasks_data:
        # Если нет диапазона анализа, использовать диапазон задач
        min_start = min(task['start'] for task in tasks_data)
        max_finish = max(task['finish'] for task in tasks_data)
        xaxis_range_start = min_start - timedelta(days=7)
        xaxis_range_end = max_finish + timedelta(days=14)
        xaxis_range = [xaxis_range_start, xaxis_range_end]
    
    # Настроить оси
    xaxis_config = dict(
        type='date',
        showgrid=True,
        gridcolor='lightgray'
    )
    
    # Добавить диапазон отображения, если он определен
    if xaxis_range:
        xaxis_config['range'] = xaxis_range
    
    fig.update_layout(
        title='Суммарный план график',
        xaxis_title='Дата',
        yaxis_title='Задачи',
        height=max(400, len(y_positions) * 30 + 100),
        hovermode='closest',
        yaxis=dict(
            tickmode='array',
            tickvals=y_positions,
            ticktext=y_labels,
            autorange='reversed',
            tickfont=dict(size=16)  # Размер шрифта равен толщине линии
        ),
        xaxis=xaxis_config,
        plot_bgcolor='white',
        margin=dict(l=100, r=50, t=50, b=50)  # Уменьшен margin left для увеличения области диаграммы
    )
    
    return fig


def _parse_date(parser, date_string):
    """Парсит строку даты в datetime объект, используя утилиту"""
    # Используем утилиту parse_date напрямую
    return parse_date(date_string)

