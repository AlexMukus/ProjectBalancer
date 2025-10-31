# Анализатор управления ресурсами

## Overview
This desktop application, built with Streamlit, analyzes Microsoft Project plan files. It parses MS Project XML files to identify workload imbalances among resources, visualizes allocation patterns with color-coded status indicators, and provides actionable recommendations for optimization. Users can filter resources, view detailed task breakdowns, and export analysis results in CSV or PDF format. The project aims to provide a quick prototyping interface focused on data analysis without complex frontend development, offering a Python-native approach to building interactive web applications for data visualization.

## Recent Changes (October 31, 2025)

**Latest Enhancements (Smart Default Dates & Resource Filtering):**
- **Default Date Range Logic**: Changed initialization from full project range to current week context:
  - Start: current date - 7 days, rounded to Monday (weekday=0)
  - End: current date + 14 days, rounded to Friday (weekday=4)
  - Dates are clamped within project bounds to prevent `StreamlitAPIException`
  - Provides focused 3-week analysis window by default
- **Resource Filter Applied Globally**: selected_resources filter now affects ALL UI sections:
  - Task details section (uses filtered display_data)
  - Recommendations (filtered_analysis created with resource filtering)
  - Workload distribution chart (uses filtered display_data)
  - Optimization suggestions (selected_resources passed to optimize_with_task_shifting)
  - Weekly timeline visualization (timeline_data filtered by keys)
  - Interactive specialist replacement (uses filtered_analysis)
- **Bug Fix**: Fixed date clamp logic to prevent defaults outside project_start...project_end bounds

**Previous Bug Fixes (Export Functionality):**
- Fixed `UnicodeEncodeError` in CSV export: Added `remove_emojis()` function to strip emoji symbols (🔴, 🟢) before cp1251 encoding, ensuring Excel compatibility
- Fixed `KeyError: 'task'` in export functions: Updated CSV/PDF exporters to use correct optimization_results structure (`task_name`, `shift_days`, `improvement`, `reason`, `priority` instead of deprecated `task`, `action`, `details`)
- Enhanced export data completeness: CSV/PDF now include 4 sections (summary, task details, weekly timeline, optimization suggestions) with proper field mapping

**Previous Critical Bug Fixes:**
- Fixed `AttributeError: 'Figure' object has no attribute 'update_xaxis'` - replaced with correct Plotly methods: `update_xaxes()` and `update_yaxes()`
- Optimized task shifting algorithm: weeks_with_dates construction moved to resource level (instead of repeating for each task)
- Improved target week determination logic: now finds ALL overlapping weeks, selects the main one with the largest task proportion
- Added real hours calculation instead of percentages only: hours_removed_from_source and hours_added_to_target
- Fixed date range filtering bug: `weeks_with_dates` in `optimize_with_task_shifting` now constructed from filtered `date_range` for consistency with timeline_data

**End-to-End Testing:**
- All core features working correctly
- Verified: file upload, smart default dates, resource filtering across all sections (task details, recommendations, charts, optimization, timeline, interactive replacement)
- Previous verifications: analysis, optimization, visualization, CSV/PDF export with emoji sanitization and correct optimization schema

## User Preferences
Предпочитаемый стиль коммуникации: Простой, повседневный язык на русском.

## System Architecture

### UI/UX Decisions
The application uses Streamlit for rapid prototyping and interactive data visualization. Plotly is utilized for interactive, professional-grade charts, enabling rich interactivity like hovering, zooming, and panning. Custom CSS, inspired by Microsoft Fluent UI, is injected to enhance the professional appearance, incorporating a Red/Yellow/Green color-coding system for quick visual assessment and a card-based layout for metrics.

### Technical Implementations
The backend processes MS Project XML files using `lxml` for robust parsing, handling large files efficiently. Data manipulation and complex resource allocation calculations are performed using Pandas DataFrames.

### Feature Specifications
- **Workload Calculation Logic**: Resources are categorized as Overloaded (>100% capacity - Red), Optimal (70-100% capacity - Green), or Underutilized (<70% capacity - Yellow) based on actual project timelines versus resource capacity.
- **Recommendation Engine**: Provides actionable suggestions for rebalancing workloads, prioritizing resources based on their overload percentage (High: >120%, Medium: 100-120%, Low: optimizing underutilized resources).
- **Intelligent Optimization**:
    - Calculates weekly resource loading, identifies peaks and troughs, and caches tasks for performance.
    - Implements a task shifting algorithm to automatically suggest optimal task shifts (1-30 days) for overloaded weeks, considering multi-week tasks and ensuring the target week does not become overloaded.
    - Offers interactive specialist replacement, allowing users to substitute overloaded resources with underutilized ones.
    - Visualizes weekly loading with Plotly bar charts, showing 100% and target loading lines, and color-coded weeks (red for overloaded, green for optimal, yellow for underutilized).
- **Report Generation**: Exports professional PDF reports using ReportLab with custom styling and CSV exports via Pandas for raw data analysis.
- **State Management**: Utilizes `st.session_state` to preserve parsed data, user selections, and analysis results across interactions.

### System Design Choices
The application is designed to be highly interactive and data-driven, leveraging Python's strengths in data processing and web application development. The choice of Streamlit and Plotly reflects a priority for quick development and rich interactive visualization.

## External Dependencies

### Core Libraries
- **Streamlit**: Web framework for interactive applications.
- **Pandas**: For tabular data manipulation and analysis.
- **lxml**: High-performance XML parser, specifically for Microsoft Project XML files.
- **Plotly**: For interactive charting and data visualization.
- **ReportLab**: For generating PDF documents.

### File Format Support
- **Microsoft Project XML**: Supports `.xml` and `.mspdi` file formats. `.mpp` files must be converted to XML from MS Project.