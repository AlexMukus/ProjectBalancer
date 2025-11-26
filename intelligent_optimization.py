"""
Модуль интеллектуальной оптимизации
Содержит функции для оптимизации распределения задач и UI компонент
"""
import streamlit as st
from datetime import datetime, timedelta
from msproject_utils import find_task_by_name_and_dates


def check_task_dependencies(task_id, new_start, new_end, parser, task_dict):
    """
    Проверяет, что сдвиг задачи не нарушает зависимости с предшественниками
    
    Returns:
        (is_valid, blocking_tasks) - можно ли сдвинуть и список блокирующих задач
    """
    task = task_dict.get(task_id)
    if not task or not task.get('predecessors'):
        return True, []  # Нет зависимостей - можно сдвигать
    
    blocking_tasks = []
    
    # Проверить все предшественники
    for pred_id in task['predecessors']:
        pred_task = task_dict.get(pred_id)
        if not pred_task or not pred_task.get('finish'):
            continue
        
        pred_end = parser._parse_date(pred_task['finish'])
        if not pred_end:
            continue
        
        # Проверить, что предшественник завершился до начала задачи
        # (простая зависимость Finish-to-Start)
        if new_start < pred_end:
            blocking_tasks.append({
                'id': pred_id,
                'name': pred_task.get('name', 'Unknown'),
                'finish': pred_end.strftime('%Y-%m-%d'),
                'required_start': pred_end.strftime('%Y-%m-%d')
            })
    
    return len(blocking_tasks) == 0, blocking_tasks


def calculate_precise_improvement(task_info, source_week, target_week, shift_days, 
                                   task_start, task_end, task_hours, weeks_with_dates, weekly_loads):
    """
    Точный расчет улучшения с учетом частичных перекрытий задачи с неделями
    
    Returns:
        (improvement_percentage, hours_removed, hours_added, is_valid)
    """
    new_start = task_start + timedelta(days=shift_days)
    new_end = task_end + timedelta(days=shift_days)
    
    # Точный расчет: сколько часов задачи было в исходной неделе
    source_overlap_start = max(task_start, source_week['start'])
    source_overlap_end = min(task_end, source_week['end'])
    
    if source_overlap_start > source_overlap_end:
        return 0, 0, 0, False
    
    task_duration_days = (task_end - task_start).days + 1
    source_overlap_days = (source_overlap_end - source_overlap_start).days + 1
    source_proportion = source_overlap_days / task_duration_days if task_duration_days > 0 else 0
    hours_removed_from_source = task_hours * source_proportion
    
    # Точный расчет: сколько часов задачи будет в целевой неделе
    target_overlap_start = max(new_start, target_week['start'])
    target_overlap_end = min(new_end, target_week['end'])
    
    if target_overlap_start > target_overlap_end:
        return 0, 0, 0, False
    
    target_overlap_days = (target_overlap_end - target_overlap_start).days + 1
    target_proportion = target_overlap_days / task_duration_days if task_duration_days > 0 else 0
    hours_added_to_target = task_hours * target_proportion
    
    # Рассчитать новую загрузку
    new_source_hours = source_week['hours'] - hours_removed_from_source
    new_source_percentage = (new_source_hours / source_week['capacity']) * 100 if source_week['capacity'] > 0 else 0
    
    new_target_hours = target_week['hours'] + hours_added_to_target
    new_target_percentage = (new_target_hours / target_week['capacity']) * 100 if target_week['capacity'] > 0 else 0
    
    # Проверка валидности
    is_valid = (new_source_percentage < source_week['percentage'] and 
                new_target_percentage <= 100)
    
    improvement = source_week['percentage'] - new_source_percentage if is_valid else 0
    
    return improvement, hours_removed_from_source, hours_added_to_target, is_valid


def binary_search_optimal_shift(task_info, source_week, target_week_idx, weekly_loads, 
                                  weeks_with_dates, parser, task_dict, max_shift, week_idx):
    """
    Бинарный поиск оптимального сдвига вместо линейного перебора
    
    Returns:
        (best_shift, best_improvement) or (None, 0)
    """
    task = task_info['task']
    task_start = task_info['start']
    task_end = task_info['end']
    task_hours = task_info['hours']
    
    if target_week_idx >= len(weekly_loads) or target_week_idx == week_idx:
        return None, 0
    
    target_week = weekly_loads[target_week_idx]
    
    # Проверка зависимостей для граничного случая
    new_start_max = task_start + timedelta(days=max_shift)
    new_end_max = task_end + timedelta(days=max_shift)
    is_valid_max, _ = check_task_dependencies(task['id'], new_start_max, new_end_max, parser, task_dict)
    
    if not is_valid_max:
        # Если максимальный сдвиг нарушает зависимости, ищем меньший
        left, right = 1, max_shift
        best_shift = None
        best_improvement = 0
        
        while left <= right:
            mid = (left + right) // 2
            new_start = task_start + timedelta(days=mid)
            new_end = task_end + timedelta(days=mid)
            
            is_valid, _ = check_task_dependencies(task['id'], new_start, new_end, parser, task_dict)
            improvement, _, _, valid_shift = calculate_precise_improvement(
                task_info, source_week, target_week, mid,
                task_start, task_end, task_hours, weeks_with_dates, weekly_loads
            )
            
            if is_valid and valid_shift and improvement > best_improvement:
                best_shift = mid
                best_improvement = improvement
                # Пробуем больший сдвиг
                left = mid + 1
            else:
                # Меньший сдвиг
                right = mid - 1
        
        return best_shift, best_improvement
    
    # Если зависимости не нарушаются, ищем оптимальный сдвиг бинарным поиском
    left, right = 1, max_shift
    best_shift = None
    best_improvement = 0
    
    while left <= right:
        mid = (left + right) // 2
        
        improvement, _, _, is_valid = calculate_precise_improvement(
            task_info, source_week, target_week, mid,
            task_start, task_end, task_hours, weeks_with_dates, weekly_loads
        )
        
        if is_valid and improvement > best_improvement:
            best_shift = mid
            best_improvement = improvement
        
        # Если улучшение растет, пробуем больший сдвиг, иначе меньший
        if mid < max_shift:
            next_improvement, _, _, next_valid = calculate_precise_improvement(
                task_info, source_week, target_week, mid + 1,
                task_start, task_end, task_hours, weeks_with_dates, weekly_loads
            )
            if next_valid and next_improvement > improvement:
                left = mid + 1
            else:
                right = mid - 1
        else:
            break
    
    return best_shift, best_improvement


def optimize_with_task_shifting(parser, settings, date_range_start=None, date_range_end=None, selected_resources=None):
    """
    Оптимизация распределения с смещением задач во времени
    
    Args:
        parser: MSProjectParser instance
        settings: Настройки оптимизации
            {
                'max_shift_days': int,  # Максимальное смещение задач в днях
                'target_load': float,   # Целевая загрузка (70-100%)
                'mode': 'balance'       # Режим: 'balance' или 'minimize_peaks'
            }
        date_range_start: Начало анализируемого периода (datetime.date or None)
        date_range_end: Конец анализируемого периода (datetime.date or None)
        selected_resources: Список выбранных ресурсов для оптимизации (list or None)
    """
    max_shift = settings.get('max_shift_days', 14)
    target_load = settings.get('target_load', 85)
    mode = settings.get('mode', 'balance')
    
    # Получить временную загрузку с учётом диапазона
    timeline_data = parser.get_timeline_workload(date_range_start, date_range_end)
    # Создать task_dict по ID только для зависимостей (не для связывания назначений)
    task_dict = {t['id']: t for t in parser.tasks}
    
    # Найти перегруженные периоды для каждого ресурса
    optimization_suggestions = []
    
    for resource_name, weekly_loads in timeline_data.items():
        # Фильтрация по выбранным ресурсам
        if selected_resources and resource_name not in selected_resources:
            continue
        # Найти перегруженные и недозагруженные недели
        overloaded_weeks = {}
        underloaded_weeks = {}
        
        for i, week_data in enumerate(weekly_loads):
            if week_data['percentage'] > 100:
                overloaded_weeks[i] = week_data
            elif week_data['percentage'] < target_load:
                underloaded_weeks[i] = week_data
        
        if not overloaded_weeks:
            continue
        
        # Найти задачи этого ресурса
        resource = next((r for r in parser.resources if r['name'] == resource_name), None)
        if not resource:
            continue
        
        # Для MultiProjectParser использовать специальный метод
        # Проверяем наличие атрибута 'parsers' вместо isinstance для избежания циклических импортов
        if hasattr(parser, 'parsers') and hasattr(parser, 'get_assignments_for_resource'):
            resource_assignments = parser.get_assignments_for_resource(resource_name)
        else:
            resource_assignments = [a for a in parser.assignments if a.get('resource_name') == resource_name]
        
        # Построить карту недель для быстрого поиска (один раз на ресурс)
        # КРИТИЧНО: Использовать тот же диапазон что и в get_timeline_workload()
        project_start = None
        project_end = None
        for task_item in parser.tasks:
            if task_item['start']:
                ts = parser._parse_date(task_item['start'])
                if ts and (project_start is None or ts < project_start):
                    project_start = ts
            if task_item['finish']:
                te = parser._parse_date(task_item['finish'])
                if te and (project_end is None or te > project_end):
                    project_end = te
        
        # Использовать выбранный диапазон или весь проект
        if date_range_start and date_range_end:
            from datetime import datetime as dt_class
            range_start_dt = dt_class.combine(date_range_start, dt_class.min.time())
            range_end_dt = dt_class.combine(date_range_end, dt_class.max.time())
        else:
            range_start_dt = project_start
            range_end_dt = project_end
        
        if not range_start_dt or not range_end_dt:
            continue
            
        current_date = range_start_dt
        weeks_with_dates = []
        while current_date <= range_end_dt:
            week_end = current_date + timedelta(days=6)
            weeks_with_dates.append({
                'start': current_date,
                'end': min(week_end, range_end_dt),
                'index': len(weeks_with_dates)
            })
            current_date = week_end + timedelta(days=1)
        
        # Для каждой перегруженной недели найти задачи, которые можно сдвинуть
        for week_idx, week_data in overloaded_weeks.items():
            excess_hours = week_data['hours'] - week_data['capacity']
            
            # Получить временные границы текущей недели
            if week_idx >= len(weeks_with_dates):
                continue
            current_week_info = weeks_with_dates[week_idx]
            week_start = current_week_info['start']
            week_end = current_week_info['end']
            
            # Найти задачи, пересекающиеся с этой неделей
            tasks_in_week = []
            for assignment in resource_assignments:
                # Поиск задачи по комбинации имени и дат
                task = find_task_by_name_and_dates(
                    parser.tasks,
                    assignment.get('task_name'),
                    assignment.get('task_start'),
                    assignment.get('task_finish')
                )
                if not task or not task.get('start') or not task.get('finish'):
                    continue
                
                task_start = parser._parse_date(task['start'])
                task_end = parser._parse_date(task['finish'])
                if not task_start or not task_end:
                    continue
                
                # КРИТИЧНО: Проверить, что задача пересекается с текущей неделей
                if task_end < week_start or task_start > week_end:
                    continue  # Задача не пересекается с этой неделей
                
                task_hours = parser._parse_work_hours(assignment['work'])
                tasks_in_week.append({
                    'task': task,
                    'assignment': assignment,
                    'start': task_start,
                    'end': task_end,
                    'hours': task_hours
                })
            
            # Приоритизация задач: сортировка по влиянию на перегрузку
            # Влияние = (часы задачи в неделе) * (процент перегрузки недели)
            def calculate_task_impact(task_info):
                task_start = task_info['start']
                task_end = task_info['end']
                
                # Найти долю задачи в перегруженной неделе
                overlap_start = max(task_start, week_start)
                overlap_end = min(task_end, week_end)
                
                if overlap_start > overlap_end:
                    return 0
                
                task_duration_days = (task_end - task_start).days + 1
                overlap_days = (overlap_end - overlap_start).days + 1
                proportion = overlap_days / task_duration_days if task_duration_days > 0 else 0
                hours_in_week = task_info['hours'] * proportion
                
                # Влияние = часы в неделе * уровень перегрузки
                impact = hours_in_week * week_data['percentage']
                return impact
            
            # Сортировка по влиянию (наибольшее влияние первым)
            tasks_in_week.sort(key=calculate_task_impact, reverse=True)
            
            # Попробовать сдвинуть задачи в недозагруженные периоды
            for task_info in tasks_in_week:
                task = task_info['task']
                task_start = task_info['start']
                task_end = task_info['end']
                task_hours = task_info['hours']
                
                best_shift = None
                best_improvement = 0
                best_target_week_idx = None
                
                # Найти подходящие целевые недели (недозагруженные)
                # Принимаем все недозагруженные недели как кандидаты
                # Бинарный поиск проверит, может ли задача достичь недели с любым сдвигом до max_shift
                candidate_target_weeks = []
                for i, target_week in enumerate(weekly_loads):
                    if i != week_idx and target_week['percentage'] < target_load:
                        candidate_target_weeks.append(i)
                
                # Для каждой целевой недели найти оптимальный сдвиг бинарным поиском
                for target_week_idx in candidate_target_weeks:
                    if target_week_idx >= len(weekly_loads):
                        continue
                    
                    target_week = weekly_loads[target_week_idx]
                    
                    # Бинарный поиск оптимального сдвига
                    shift, improvement = binary_search_optimal_shift(
                        task_info, week_data, target_week_idx, weekly_loads,
                        weeks_with_dates, parser, task_dict, max_shift, week_idx
                    )
                    
                    if shift and improvement > best_improvement:
                        # Проверить зависимости для найденного сдвига
                        new_start_check = task_start + timedelta(days=shift)
                        new_end_check = task_end + timedelta(days=shift)
                        is_valid, blocking = check_task_dependencies(
                            task['id'], new_start_check, new_end_check, parser, task_dict
                        )
                        
                        if is_valid:
                            best_improvement = improvement
                            best_shift = shift
                            best_target_week_idx = target_week_idx
                        elif shift > 1:
                            # Если зависимости нарушены, попробовать меньший сдвиг
                            for smaller_shift in range(1, shift):
                                new_start_small = task_start + timedelta(days=smaller_shift)
                                new_end_small = task_end + timedelta(days=smaller_shift)
                                is_valid_small, _ = check_task_dependencies(
                                    task['id'], new_start_small, new_end_small, parser, task_dict
                                )
                                if is_valid_small:
                                    improvement_small, _, _, valid = calculate_precise_improvement(
                                        task_info, week_data, target_week, smaller_shift,
                                        task_start, task_end, task_hours, weeks_with_dates, weekly_loads
                                    )
                                    if valid and improvement_small > best_improvement:
                                        best_improvement = improvement_small
                                        best_shift = smaller_shift
                                        best_target_week_idx = target_week_idx
                                        break
                
                # Если нашли хороший сдвиг, добавляем рекомендацию
                if best_shift and best_target_week_idx is not None:
                    new_start = task_start + timedelta(days=best_shift)
                    new_end = task_end + timedelta(days=best_shift)
                    
                    # Точный расчет для финальной рекомендации
                    target_week_final = weekly_loads[best_target_week_idx]
                    _, hours_removed, hours_added, _ = calculate_precise_improvement(
                        task_info, week_data, target_week_final, best_shift,
                        task_start, task_end, task_hours, weeks_with_dates, weekly_loads
                    )
                    
                    optimization_suggestions.append({
                        'type': 'shift_task',
                        'resource': resource_name,
                        'task_name': task['name'],
                        'task_hours': task_hours,
                        'original_start': task_start.strftime('%Y-%m-%d'),
                        'original_end': task_end.strftime('%Y-%m-%d'),
                        'suggested_start': new_start.strftime('%Y-%m-%d'),
                        'suggested_end': new_end.strftime('%Y-%m-%d'),
                        'shift_days': best_shift,
                        'improvement': f'{best_improvement:.1f}%',
                        'hours_freed': f'{hours_removed:.1f}',
                        'hours_added': f'{hours_added:.1f}',
                        'reason': f'Снизить перегрузку на {hours_removed:.1f}ч в неделю {week_data["week"]} (точный расчет)',
                        'priority': 'Высокий' if week_data['percentage'] > 120 else 'Средний'
                    })
                    
                    # Для режима balance берём только одну задачу на неделю
                    if mode == 'balance':
                        break
    
    return optimization_suggestions


def render_intelligent_optimization(selected_resources):
    """
    UI компонент для интеллектуальной оптимизации
    
    Args:
        selected_resources: список выбранных ресурсов для оптимизации
    """
    # Оптимизация с смещением задач
    st.markdown("---")
    st.markdown("## ⚙️ Интеллектуальная оптимизация")
    
    with st.expander("🎯 Настройки оптимизации", expanded=True):
        col_opt1, col_opt2, col_opt3 = st.columns(3)
        
        with col_opt1:
            max_shift_days = st.slider(
                "Максимальное смещение задач (дни)",
                min_value=1,
                max_value=30,
                value=14,
                help="Насколько далеко можно сдвигать задачи для оптимизации"
            )
        
        with col_opt2:
            target_load = st.slider(
                "Целевая загрузка (%)",
                min_value=70,
                max_value=100,
                value=85,
                help="Желаемый уровень загрузки ресурсов"
            )
        
        with col_opt3:
            opt_mode = st.selectbox(
                "Режим оптимизации",
                options=['balance', 'minimize_peaks'],
                format_func=lambda x: 'Балансировка загрузки' if x == 'balance' else 'Минимизация пиков',
                help="Стратегия оптимизации распределения"
            )
        
        if st.button("🚀 Запустить оптимизацию", use_container_width=True):
            with st.spinner("Расчёт оптимального распределения..."):
                optimization_settings = {
                    'max_shift_days': max_shift_days,
                    'target_load': target_load,
                    'mode': opt_mode
                }
                st.session_state.optimization_results = optimize_with_task_shifting(
                    st.session_state.parser, 
                    optimization_settings,
                    st.session_state.date_range_start,
                    st.session_state.date_range_end,
                    selected_resources
                )
                st.session_state.timeline_data = st.session_state.parser.get_timeline_workload(
                    st.session_state.date_range_start,
                    st.session_state.date_range_end
                )
                st.success("✓ Оптимизация завершена!")
                st.rerun()
    
    # Показать результаты оптимизации
    if st.session_state.optimization_results:
        st.markdown("### 📈 Предложения по смещению задач")
        
        opt_results = st.session_state.optimization_results
        if opt_results:
            for i, suggestion in enumerate(opt_results[:10], 1):
                priority_color = {
                    'Высокий': '#FF4B4B',
                    'Средний': '#FFB900',
                    'Низкий': '#107C10'
                }.get(suggestion.get('priority', 'Низкий'), '#107C10')
                
                improvement_info = f"<b>Улучшение:</b> {suggestion['improvement']}<br/>" if 'improvement' in suggestion else ""
                st.markdown(f"""
                <div style='background-color: white; padding: 15px; border-radius: 8px; 
                            margin: 10px 0; border-left: 4px solid {priority_color}'>
                    <b>{i}. Сдвинуть задачу "{suggestion['task_name']}"</b> 
                    <span style='background-color: {priority_color}; color: white; 
                                 padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                        {suggestion['priority']}
                    </span><br/>
                    <b>Ресурс:</b> {suggestion['resource']}<br/>
                    <b>Объём работы:</b> {suggestion['task_hours']:.1f} часов<br/>
                    <b>Текущие даты:</b> {suggestion['original_start']} → {suggestion['original_end']}<br/>
                    <b>Предлагаемые даты:</b> {suggestion['suggested_start']} → {suggestion['suggested_end']} 
                    (сдвиг на {suggestion['shift_days']} дн.)<br/>
                    {improvement_info}
                    <b>Причина:</b> {suggestion['reason']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✓ Распределение оптимально, смещения не требуются!")

