# Анализатор управления ресурсами

## Overview
This desktop application, built with Streamlit, analyzes Microsoft Project plan files. It parses MS Project XML files to identify workload imbalances among resources, visualizes allocation patterns with color-coded status indicators, and provides actionable recommendations for optimization. Users can filter resources, view detailed task breakdowns, and export analysis results in CSV or PDF format. The project aims to provide a quick prototyping interface focused on data analysis without complex frontend development, offering a Python-native approach to building interactive web applications for data visualization.

## Recent Changes (November 1, 2025)

**Latest Fix (.exe Build - PackageNotFoundError & Compilation Errors - November 1, 2025):**
- **Problem Solved**: Fixed critical `importlib.metadata.PackageNotFoundError` when running MSProjectAnalyzer.exe
- **Root Cause**: PyInstaller wasn't including package metadata (version info) that Streamlit checks at runtime
- **Solution Implemented**:
  - Updated `app.spec`: Added `copy_metadata()` calls for all libraries (streamlit, pandas, plotly, altair, lxml, reportlab, openpyxl, python-dateutil, pyarrow, click, validators, watchdog, tornado)
  - Updated `build_exe.bat`: 
    - Added `--only-binary :all:` for pandas and pyarrow installation (prevents Windows compilation errors)
    - Separated dependency installation: first pip/wheel/setuptools upgrade, then pandas/pyarrow binaries, then remaining packages
    - Added clear error messages and 64-bit Python verification hints
  - Updated `BUILD_INSTRUCTIONS.md`: Added troubleshooting sections for:
    - PackageNotFoundError with clear explanation and rebuild steps
    - Windows compilation errors (pandas/pyarrow) with --only-binary solutions
    - 64-bit Python verification and Microsoft C++ Build Tools guidance
- **Testing**: Architect-reviewed, user successfully built .exe after fixes
- **Files Modified**: app.spec (copy_metadata), build_exe.bat (--only-binary installation), BUILD_INSTRUCTIONS.md (troubleshooting)

**Previous Enhancement (Display Mode Switcher - October 31, 2025):**
- **Display Mode Toggle**: Added switchable display mode for workload visualization with two options:
  - **В процентах (Percentage mode)**: Default mode showing workload as percentage of capacity
    - Analysis table column: "Нагрузка %" with values like "85.5%"
    - Chart Y-axis: "Процент нагрузки (%)"
    - Threshold lines: 100% (overloaded) and 70% (underutilized)
  - **В часах (Hours mode)**: Shows workload in absolute hours
    - Analysis table column: "Загрузка (часы)" with values like "68.4 ч."
    - Chart Y-axis: "Загрузка (часы)"
    - Threshold lines: calculated based on average capacity per resource
- **Implementation Details**:
  - Radio button control in sidebar: "Отображение загрузки"
  - Mode stored in `st.session_state.display_mode` ('percentage' or 'hours')
  - Triggers automatic page reload (st.rerun) with full state persistence
  - Affects all visualization components: analysis table, workload distribution chart, weekly timeline chart
- **Export Support**: CSV and PDF export functions updated to handle both display modes
  - Status determination based on percentage calculation regardless of display mode
  - Column headers and values adapt to selected mode
- **Testing**: E2E verified both modes work correctly with seamless switching across all components

**Previous Enhancements (Resource Groups, Period Analytics & Actual Hours):**
- **Resource Groups Management**: Added complete workflow for managing custom resource groups:
  - Create groups with custom names and selected resources
  - Save groups in session state (persist during session)
  - Apply groups via explicit button with UI refresh (st.rerun)
  - Delete groups with automatic cleanup of applied state
  - Expander-based UI for group creation and management
- **Period Analysis Panel**: Added control panel displaying:
  - Selected date range (formatted as DD.MM.YYYY - DD.MM.YYYY)
  - Business days count (excluding weekends: Saturday, Sunday)
  - Work capacity per person (business_days × 8 hours)
  - Implemented `calculate_business_days()` and `calculate_work_capacity()` helper functions
- **Actual Working Hours**: New column "Рабочие часы за период" in analysis table:
  - Calculates actual hours for each resource within selected date range
  - Uses proportional allocation for tasks spanning multiple periods
  - Implemented `calculate_actual_hours_per_resource()` function
- **Enhanced CSV/PDF Export**: Exports now include:
  - Period information header (dates, business days, capacity)
  - New "Рабочие часы за период" / "Часы за период" column in resource tables
  - Updated export function signatures with period parameters
- **Bug Fixes**: 
  - Fixed `KeyError: 'start_date'` in `calculate_actual_hours_per_resource`: now uses task.get('start')/task.get('finish') and parser.assignments
  - Fixed group application flow: added "Применить группу" button with proper st.rerun() behavior

**Previous Enhancements (Smart Default Dates & Resource Filtering):**
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
The application uses Streamlit for rapid prototyping and interactive data visualization. Plotly is utilized for interactive, professional-grade charts, enabling rich interactivity like hovering, zooming, and panning. 

**Design System**: The application uses Material Design 3 (MD3) as its single design system:
- **Material Design 3**: Google's MD3 design system with elevated cards, rounded corners, modern typography, and a purple-blue color palette generated from seed color #0078D4
  - Colors: Primary #005EB0, Error #BA1A1A, Tertiary #6D5677, Surface #FEF7FF
  - Modular components defined in `md3_components.py`
  - Elevated metric cards, alternating row styles, and hover effects
  - Red/Yellow/Green color-coding system for workload status (overloaded/underutilized/optimal)

**Display Modes**: Users can switch between two display modes for workload visualization:
- **В процентах (Percentage)**: Shows workload as percentage of capacity (default)
- **В часах (Hours)**: Shows workload in absolute hours
- Mode selection stored in `st.session_state.display_mode` and triggers automatic page reload with full state preservation

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