# Resource Management Analyzer

A professional desktop-based application for analyzing Microsoft Project plan files to identify workload imbalances and provide optimization recommendations.

## Features

- **MS Project File Support**: Upload and parse Microsoft Project XML files (.xml, .mspdi)
- **Intelligent Workload Calculation**: Analyzes resource allocation based on actual project timelines and resource capacity
- **Personnel Search**: Filter and search tasks by resource names and surnames
- **Visual Analysis**: Color-coded status indicators for quick identification of resource issues
  - 🔴 Red: Overloaded (>100% capacity)
  - 🟢 Green: Optimal (70-100% capacity)
  - 🟡 Yellow: Underutilized (<70% capacity)
- **Smart Recommendations**: Actionable suggestions for workload balancing
- **Export Options**: Download analysis as CSV or PDF reports

## How to Use

### 1. Prepare Your MS Project File

If you have a .mpp file, convert it to XML format:
1. Open your project in Microsoft Project
2. Go to **File → Save As**
3. Select **XML Format (*.xml)** as the file type
4. Save the file

### 2. Upload and Analyze

1. Click "Choose file" in the sidebar
2. Select your MS Project XML file
3. Click "Parse File" to analyze the data
4. Review the workload analysis dashboard

### 3. Filter and Search

- Use the search box to filter resources by name or surname
- Select specific resources using the multi-select dropdown
- Expand individual resources to see detailed task breakdowns

### 4. Review Recommendations

The system provides prioritized recommendations:
- **High Priority**: Resources over 120% capacity
- **Medium Priority**: Resources between 100-120% capacity
- **Low Priority**: Optimization suggestions for underutilized resources

### 5. Export Results

Download your analysis as:
- **CSV**: For further analysis in Excel or other tools
- **PDF**: Professional report for presentations

## Workload Calculation

The application calculates workload percentages based on:

- **Project Duration**: Automatically detected from task start/end dates
- **Resource Capacity**: Based on MaxUnits and standard 40-hour work weeks (5 days × 8 hours)
- **Task Assignments**: Total hours allocated to each resource

**Capacity Model**:
- Calendar days are converted to workdays using a 5/7 ratio (assuming 5-day work week)
- Each workday provides 8 hours of working capacity (matching MS Project's P1D = 8 hours)
- Resource capacity = Available work hours × MaxUnits

**Formula**: `Workload % = (Total Assigned Hours / Capacity) × 100`

**Examples** (for MaxUnits = 1.0):
- 1 calendar day → 0.71 workdays → 5.71 work hours capacity
- 7 calendar days → 5 workdays → 40 work hours capacity
- 28 calendar days → 20 workdays → 160 work hours capacity

## Color Scheme

Following Microsoft Project design guidelines:
- Primary Blue: #0078D4
- Success Green: #107C10
- Warning Red: #FF4B4B
- Background Grey: #F3F2F1
- Text Charcoal: #323130

## Sample Data

A sample project file (`sample_project.xml`) is included for testing. It demonstrates:
- 5 resources with varying workloads
- 8 tasks with different durations
- Resource assignments showing overload and underutilization scenarios

## Technical Details

- Built with Streamlit for interactive web interface
- Uses lxml for robust XML parsing
- Plotly for interactive visualizations
- ReportLab for PDF generation
- Pandas for data manipulation

## Support

For issues with:
- **File parsing**: Ensure your XML file is properly formatted MS Project export
- **Date calculations**: Verify that tasks have valid Start and Finish dates
- **Missing resources**: Check that resources are properly assigned in the source project
