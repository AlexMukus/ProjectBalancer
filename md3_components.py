"""
Material Design 3 Theme Components
Современный дизайн на основе Material Design 3 с палитрой из #0078D4
"""

import streamlit as st

# MD3 цветовая палитра, сгенерированная из seed color #0078D4
MD3_COLORS = {
    # Light theme colors
    'primary': '#005EB0',
    'on_primary': '#FFFFFF',
    'primary_container': '#D1E4FF',
    'on_primary_container': '#001B3D',
    
    'secondary': '#545F71',
    'on_secondary': '#FFFFFF',
    'secondary_container': '#D8E3F8',
    'on_secondary_container': '#111C2B',
    
    'tertiary': '#6D5677',
    'on_tertiary': '#FFFFFF',
    'tertiary_container': '#F5D9FF',
    'on_tertiary_container': '#271431',
    
    'error': '#BA1A1A',
    'on_error': '#FFFFFF',
    'error_container': '#FFDAD6',
    'on_error_container': '#410002',
    
    'background': '#FDFBFF',
    'on_background': '#1A1C1E',
    'surface': '#FDFBFF',
    'on_surface': '#1A1C1E',
    'surface_variant': '#DFE2EB',
    'on_surface_variant': '#43474E',
    
    'outline': '#73777F',
    'outline_variant': '#C3C6CF',
}

def get_md3_css():
    """Возвращает CSS стили для темы Material Design 3"""
    return """
    <style>
        /* Используем системные шрифты для работы в .exe (без внешних зависимостей) */
        /* Roboto будет использован если доступен, иначе fallback на системные шрифты */
        
        /* MD3 Color Variables */
        :root {{
            --md-sys-color-primary: {MD3_COLORS['primary']};
            --md-sys-color-on-primary: {MD3_COLORS['on_primary']};
            --md-sys-color-primary-container: {MD3_COLORS['primary_container']};
            --md-sys-color-on-primary-container: {MD3_COLORS['on_primary_container']};
            
            --md-sys-color-secondary: {MD3_COLORS['secondary']};
            --md-sys-color-on-secondary: {MD3_COLORS['on_secondary']};
            --md-sys-color-secondary-container: {MD3_COLORS['secondary_container']};
            --md-sys-color-on-secondary-container: {MD3_COLORS['on_secondary_container']};
            
            --md-sys-color-tertiary: {MD3_COLORS['tertiary']};
            --md-sys-color-on-tertiary: {MD3_COLORS['on_tertiary']};
            --md-sys-color-tertiary-container: {MD3_COLORS['tertiary_container']};
            --md-sys-color-on-tertiary-container: {MD3_COLORS['on_tertiary_container']};
            
            --md-sys-color-error: {MD3_COLORS['error']};
            --md-sys-color-on-error: {MD3_COLORS['on_error']};
            --md-sys-color-error-container: {MD3_COLORS['error_container']};
            --md-sys-color-on-error-container: {MD3_COLORS['on_error_container']};
            
            --md-sys-color-background: {MD3_COLORS['background']};
            --md-sys-color-on-background: {MD3_COLORS['on_background']};
            --md-sys-color-surface: {MD3_COLORS['surface']};
            --md-sys-color-on-surface: {MD3_COLORS['on_surface']};
            --md-sys-color-surface-variant: {MD3_COLORS['surface_variant']};
            --md-sys-color-on-surface-variant: {MD3_COLORS['on_surface_variant']};
            
            --md-sys-color-outline: {MD3_COLORS['outline']};
            --md-sys-color-outline-variant: {MD3_COLORS['outline_variant']};
        }}
        
        /* MD3 Typography Scale */
        .md3-display-large {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 57px;
            font-weight: 400;
            line-height: 64px;
            letter-spacing: -0.25px;
        }}
        
        .md3-display-medium {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 45px;
            font-weight: 400;
            line-height: 52px;
            letter-spacing: 0;
        }}
        
        .md3-display-small {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 36px;
            font-weight: 400;
            line-height: 44px;
            letter-spacing: 0;
        }}
        
        .md3-headline-large {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 32px;
            font-weight: 400;
            line-height: 40px;
            letter-spacing: 0;
        }}
        
        .md3-headline-medium {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 28px;
            font-weight: 400;
            line-height: 36px;
            letter-spacing: 0;
        }}
        
        .md3-headline-small {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 24px;
            font-weight: 400;
            line-height: 32px;
            letter-spacing: 0;
        }}
        
        .md3-title-large {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 22px;
            font-weight: 400;
            line-height: 28px;
            letter-spacing: 0;
        }}
        
        .md3-title-medium {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 16px;
            font-weight: 500;
            line-height: 24px;
            letter-spacing: 0.15px;
        }}
        
        .md3-title-small {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            line-height: 20px;
            letter-spacing: 0.1px;
        }}
        
        .md3-body-large {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 16px;
            font-weight: 400;
            line-height: 24px;
            letter-spacing: 0.5px;
        }}
        
        .md3-body-medium {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 400;
            line-height: 20px;
            letter-spacing: 0.25px;
        }}
        
        .md3-body-small {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 12px;
            font-weight: 400;
            line-height: 16px;
            letter-spacing: 0.4px;
        }}
        
        .md3-label-large {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            line-height: 20px;
            letter-spacing: 0.1px;
        }}
        
        .md3-label-medium {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 12px;
            font-weight: 500;
            line-height: 16px;
            letter-spacing: 0.5px;
        }}
        
        .md3-label-small {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 11px;
            font-weight: 500;
            line-height: 16px;
            letter-spacing: 0.5px;
        }}
        
        /* MD3 App Styling */
        .stApp {{
            background-color: var(--md-sys-color-background);
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
        }}
        
        /* MD3 Headers */
        h1 {{
            color: var(--md-sys-color-on-background);
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 28px;
            font-weight: 400;
            line-height: 36px;
        }}
        
        h2 {{
            color: var(--md-sys-color-on-background);
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 24px;
            font-weight: 400;
            line-height: 32px;
        }}
        
        h3 {{
            color: var(--md-sys-color-on-background);
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 22px;
            font-weight: 400;
            line-height: 28px;
        }}
        
        /* MD3 Elevated Card */
        .md3-card {{
            background-color: var(--md-sys-color-surface);
            border-radius: 12px;
            padding: 24px;
            margin: 16px 0;
            box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.3), 
                        0px 1px 3px 1px rgba(0, 0, 0, 0.15);
            transition: box-shadow 0.3s ease;
        }}
        
        .md3-card:hover {{
            box-shadow: 0px 2px 6px 2px rgba(0, 0, 0, 0.15), 
                        0px 1px 2px 0px rgba(0, 0, 0, 0.30);
        }}
        
        /* MD3 Buttons */
        .md3-filled-button {{
            background-color: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
            border: none;
            border-radius: 20px;
            padding: 10px 24px;
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.3), 
                        0px 1px 3px 1px rgba(0, 0, 0, 0.15);
        }}
        
        .md3-filled-button:hover {{
            box-shadow: 0px 1px 3px 1px rgba(0, 0, 0, 0.15), 
                        0px 1px 2px 0px rgba(0, 0, 0, 0.30);
            background-color: #004a8f;
        }}
        
        .md3-outlined-button {{
            background-color: transparent;
            color: var(--md-sys-color-primary);
            border: 1px solid var(--md-sys-color-outline);
            border-radius: 20px;
            padding: 10px 24px;
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .md3-outlined-button:hover {{
            background-color: rgba(0, 94, 176, 0.08);
        }}
        
        .md3-text-button {{
            background-color: transparent;
            color: var(--md-sys-color-primary);
            border: none;
            border-radius: 20px;
            padding: 10px 12px;
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .md3-text-button:hover {{
            background-color: rgba(0, 94, 176, 0.08);
        }}
        
        /* MD3 Dataframe Styling */
        .dataframe {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            border-radius: 12px;
            overflow: hidden;
        }}
        
        .dataframe thead tr th {{
            background-color: var(--md-sys-color-surface-variant);
            color: var(--md-sys-color-on-surface-variant);
            font-weight: 500;
            padding: 12px 16px;
        }}
        
        .dataframe tbody tr:nth-child(even) {{
            background-color: var(--md-sys-color-surface-variant);
        }}
        
        .dataframe tbody tr:hover {{
            background-color: rgba(0, 94, 176, 0.08);
        }}
        
        .dataframe tbody tr td {{
            padding: 12px 16px;
        }}
    </style>
    """


def md3_metric_card(icon, value, label, description=""):
    """
    Создает MD3 метрику в стиле Elevated Card
    
    Args:
        icon: Эмодзи иконка
        value: Значение метрики
        label: Название метрики
        description: Дополнительное описание (опционально)
    """
    desc_html = f'<div class="md3-body-small" style="color: var(--md-sys-color-on-surface-variant); margin-top: 4px;">{description}</div>' if description else ''
    
    return f"""
    <div class="md3-card" style="text-align: center;">
        <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
        <div class="md3-display-small" style="color: var(--md-sys-color-on-surface); margin-bottom: 4px;">{value}</div>
        <div class="md3-label-medium" style="color: var(--md-sys-color-on-surface-variant);">{label}</div>
        {desc_html}
    </div>
    """


def md3_info_panel(period_text, business_days, capacity_hours):
    """
    Создает панель управления периодом в MD3 стиле
    
    Args:
        period_text: Текст периода анализа
        business_days: Количество рабочих дней
        capacity_hours: Рабочая ёмкость в часах
    """
    return f"""
    <div style="margin: 24px 0;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
            {md3_metric_card("📅", period_text, "Период анализа")}
            {md3_metric_card("📊", f"{business_days} дн.", "Рабочие дни", "Пн-Пт")}
            {md3_metric_card("⏱️", f"{capacity_hours} ч", "Ёмкость на чел.", f"{business_days} × 8 часов")}
        </div>
    </div>
    """


def md3_chip(text, closeable=False, chip_id=""):
    """
    Создает MD3 Chip компонент
    
    Args:
        text: Текст чипа
        closeable: Может ли чип быть удален
        chip_id: ID чипа для идентификации при удалении
    """
    close_btn = f'<button class="md3-chip-close" onclick="removeChip(\'{chip_id}\')">×</button>' if closeable else ''
    
    return f"""
    <div class="md3-chip" id="{chip_id}">
        <span class="md3-label-large">{text}</span>
        {close_btn}
    </div>
    """


def get_md3_table_style():
    """Возвращает CSS для стилизации таблиц в MD3"""
    return """
    <style>
        /* MD3 Table Container */
        .stDataFrame {{
            border-radius: 12px;
            overflow: hidden;
        }}
        
        /* Status colors - MD3 style */
        .status-overloaded {{
            background-color: var(--md-sys-color-error-container);
            color: var(--md-sys-color-on-error-container);
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 12px;
            display: inline-block;
        }}
        
        .status-optimal {{
            background-color: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 12px;
            display: inline-block;
        }}
        
        .status-underutilized {{
            background-color: var(--md-sys-color-tertiary-container);
            color: var(--md-sys-color-on-tertiary-container);
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 12px;
            display: inline-block;
        }}
    </style>
    """


def get_md3_chart_colors():
    """Возвращает MD3 цвета для графиков Plotly"""
    return {
        'overloaded': MD3_COLORS['error'],
        'optimal': MD3_COLORS['primary'],
        'underutilized': MD3_COLORS['tertiary'],
        'background': MD3_COLORS['surface'],
        'text': MD3_COLORS['on_surface'],
    }
