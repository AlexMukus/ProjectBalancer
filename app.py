import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Page configuration
st.set_page_config(
    page_title="Resource Management Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Microsoft-inspired styling
st.markdown("""
<style>
    /* Color scheme variables */
    :root {
        --primary-blue: #0078D4;
        --success-green: #107C10;
        --warning-red: #FF4B4B;
        --background-grey: #F3F2F1;
        --text-charcoal: #323130;
        --accent-purple: #5C2E91;
        --warning-yellow: #FFB900;
    }
    
    /* Main styling */
    .stApp {
        background-color: var(--background-grey);
    }
    
    /* Headers */
    h1, h2, h3 {
        color: var(--text-charcoal);
        font-family: 'Segoe UI', 'Inter', sans-serif;
    }
    
    /* Metric cards */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    /* Status badges */
    .status-overloaded {
        background-color: #FF4B4B;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .status-optimal {
        background-color: #107C10;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    .status-underutilized {
        background-color: #FFB900;
        color: white;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: var(--primary-blue);
        color: white;
        border-radius: 4px;
        border: none;
        padding: 8px 16px;
        font-weight: 500;
    }
    
    .stButton > button:hover {
        background-color: #005A9E;
    }
    
    /* Data tables */
    .dataframe {
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 14px;
    }
    
    /* File uploader */
    .uploadedFile {
        border-color: var(--primary-blue);
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: white;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# MS Project XML Parser
class MSProjectParser:
    """Parser for MS Project XML files (.xml, .mspdi)"""
    
    def __init__(self, file_content):
        self.file_content = file_content
        self.tasks = []
        self.resources = []
        self.assignments = []
        
    def parse(self):
        """Parse MS Project XML file"""
        try:
            tree = etree.parse(io.BytesIO(self.file_content))
            root = tree.getroot()
            
            # Get namespace
            namespace = {'ns': root.nsmap[None]} if None in root.nsmap else {}
            
            # Parse resources
            self.resources = self._parse_resources(root, namespace)
            
            # Parse tasks
            self.tasks = self._parse_tasks(root, namespace)
            
            # Parse assignments
            self.assignments = self._parse_assignments(root, namespace)
            
            return True
        except Exception as e:
            st.error(f"Error parsing MS Project file: {str(e)}")
            return False
    
    def _parse_resources(self, root, namespace):
        """Parse resource information"""
        resources = []
        resource_elements = root.findall('.//ns:Resource', namespace) if namespace else root.findall('.//Resource')
        
        for resource in resource_elements:
            resource_id = self._get_text(resource, 'ns:UID' if namespace else 'UID', namespace)
            name = self._get_text(resource, 'ns:Name' if namespace else 'Name', namespace)
            
            if resource_id and name:
                resources.append({
                    'id': resource_id,
                    'name': name,
                    'max_units': self._get_text(resource, 'ns:MaxUnits' if namespace else 'MaxUnits', namespace, default='1.0')
                })
        
        return resources
    
    def _parse_tasks(self, root, namespace):
        """Parse task information"""
        tasks = []
        task_elements = root.findall('.//ns:Task', namespace) if namespace else root.findall('.//Task')
        
        for task in task_elements:
            task_id = self._get_text(task, 'ns:UID' if namespace else 'UID', namespace)
            name = self._get_text(task, 'ns:Name' if namespace else 'Name', namespace)
            
            if task_id and name:
                tasks.append({
                    'id': task_id,
                    'name': name,
                    'start': self._get_text(task, 'ns:Start' if namespace else 'Start', namespace),
                    'finish': self._get_text(task, 'ns:Finish' if namespace else 'Finish', namespace),
                    'duration': self._get_text(task, 'ns:Duration' if namespace else 'Duration', namespace),
                    'work': self._get_text(task, 'ns:Work' if namespace else 'Work', namespace)
                })
        
        return tasks
    
    def _parse_assignments(self, root, namespace):
        """Parse resource assignments"""
        assignments = []
        assignment_elements = root.findall('.//ns:Assignment', namespace) if namespace else root.findall('.//Assignment')
        
        for assignment in assignment_elements:
            task_uid = self._get_text(assignment, 'ns:TaskUID' if namespace else 'TaskUID', namespace)
            resource_uid = self._get_text(assignment, 'ns:ResourceUID' if namespace else 'ResourceUID', namespace)
            work = self._get_text(assignment, 'ns:Work' if namespace else 'Work', namespace)
            
            if task_uid and resource_uid:
                assignments.append({
                    'task_id': task_uid,
                    'resource_id': resource_uid,
                    'work': work,
                    'units': self._get_text(assignment, 'ns:Units' if namespace else 'Units', namespace, default='1.0')
                })
        
        return assignments
    
    def _get_text(self, element, tag, namespace, default=''):
        """Helper to get text from XML element"""
        try:
            found = element.find(tag, namespace) if namespace else element.find(tag)
            return found.text if found is not None and found.text else default
        except:
            return default
    
    def get_resource_workload_data(self):
        """Calculate workload data for each resource"""
        workload_data = []
        
        # Calculate project timeframe for capacity calculation
        project_start = None
        project_end = None
        
        for task in self.tasks:
            if task['start']:
                task_start = self._parse_date(task['start'])
                if task_start and (project_start is None or task_start < project_start):
                    project_start = task_start
            
            if task['finish']:
                task_end = self._parse_date(task['finish'])
                if task_end and (project_end is None or task_end > project_end):
                    project_end = task_end
        
        # Calculate total available work hours for the project
        # MS Project model: 1 workday (P1D) = 8 hours
        # Default capacity for resources is 8 hours per workday
        if project_start and project_end:
            project_duration = project_end - project_start
            calendar_days = project_duration.total_seconds() / (24 * 3600)
            
            if calendar_days <= 0:
                # Minimum: 1 workday
                available_work_hours_base = 8
            else:
                # Count workdays (approximate: 5/7 of calendar days are workdays)
                workdays = calendar_days * (5.0 / 7.0)
                # 8 hours per workday
                available_work_hours_base = workdays * 8
        else:
            # Default: 4 weeks = 20 workdays = 160 hours
            available_work_hours_base = 160
        
        for resource in self.resources:
            # Get all assignments for this resource
            resource_assignments = [a for a in self.assignments if a['resource_id'] == resource['id']]
            
            # Calculate total work hours
            total_work_hours = 0
            task_details = []
            
            for assignment in resource_assignments:
                # Get task info
                task = next((t for t in self.tasks if t['id'] == assignment['task_id']), None)
                if task:
                    work_hours = self._parse_work_hours(assignment['work'])
                    total_work_hours += work_hours
                    task_details.append({
                        'task_name': task['name'],
                        'work_hours': work_hours,
                        'start': task.get('start', 'N/A'),
                        'finish': task.get('finish', 'N/A')
                    })
            
            # Calculate capacity based on resource MaxUnits and available work hours
            max_units = float(resource.get('max_units', 1.0))
            # Capacity = available work hours × max_units
            max_capacity = available_work_hours_base * max_units
            workload_percentage = (total_work_hours / max_capacity) * 100 if max_capacity > 0 else 0
            
            # Calculate project weeks for display purposes
            project_weeks = available_work_hours_base / 40
            
            workload_data.append({
                'resource_name': resource['name'],
                'total_work_hours': total_work_hours,
                'max_capacity': max_capacity,
                'workload_percentage': workload_percentage,
                'task_count': len(resource_assignments),
                'tasks': task_details,
                'project_weeks': project_weeks
            })
        
        return workload_data
    
    def _parse_date(self, date_string):
        """Parse date string to datetime object"""
        if not date_string:
            return None
        
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            try:
                # Try common MS Project formats
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(date_string, fmt)
                    except:
                        continue
            except:
                pass
        
        return None
    
    def _parse_work_hours(self, work_string):
        """Parse work hours from MS Project ISO-8601 duration format (e.g., PT8H0M0S, P2DT4H0M0S)"""
        if not work_string:
            return 0
        
        try:
            # MS Project uses ISO-8601 duration format: P[n]DT[n]H[n]M[n]S
            # P2DT4H30M0S = 2 days, 4 hours, 30 minutes
            hours = 0
            
            if work_string.startswith('P'):
                # Extract days (assuming 8-hour workdays)
                if 'D' in work_string:
                    d_start = 1  # After 'P'
                    d_end = work_string.index('D')
                    days = float(work_string[d_start:d_end])
                    hours += days * 8  # 8-hour workday
                
                # Extract hours
                if 'H' in work_string:
                    # Find start position (after 'T' or 'D')
                    if 'T' in work_string:
                        h_start = work_string.index('T') + 1
                    else:
                        h_start = work_string.index('D') + 1
                    h_end = work_string.index('H')
                    # Extract the number between start and 'H'
                    h_str = work_string[h_start:h_end]
                    # Remove any non-digit characters except '.'
                    h_str = ''.join(c for c in h_str if c.isdigit() or c == '.')
                    if h_str:
                        hours += float(h_str)
                
                # Extract minutes
                if 'M' in work_string and 'T' in work_string:
                    m_start = work_string.index('H') + 1 if 'H' in work_string else work_string.index('T') + 1
                    m_end = work_string.index('M')
                    m_str = work_string[m_start:m_end]
                    m_str = ''.join(c for c in m_str if c.isdigit() or c == '.')
                    if m_str:
                        minutes = float(m_str)
                        hours += minutes / 60
                
                return hours
            else:
                # Try to parse as number
                return float(work_string)
        except Exception as e:
            # Fallback to 0 if parsing fails
            return 0

# Analysis functions
def analyze_workload(workload_data):
    """Analyze workload and categorize resources"""
    analysis = {
        'overloaded': [],
        'optimal': [],
        'underutilized': []
    }
    
    for item in workload_data:
        percentage = item['workload_percentage']
        if percentage > 100:
            analysis['overloaded'].append(item)
        elif percentage >= 70:
            analysis['optimal'].append(item)
        else:
            analysis['underutilized'].append(item)
    
    return analysis

def generate_recommendations(analysis):
    """Generate actionable recommendations based on actual resource capacity"""
    recommendations = []
    
    overloaded = analysis['overloaded']
    underutilized = analysis['underutilized']
    
    if overloaded and underutilized:
        for overloaded_resource in overloaded:
            for underutilized_resource in underutilized:
                # Calculate excess hours based on actual capacity
                overload_percentage = overloaded_resource['workload_percentage'] - 100
                excess_hours = (overload_percentage / 100) * overloaded_resource['max_capacity']
                
                # Calculate available capacity
                underutil_percentage = 100 - underutilized_resource['workload_percentage']
                available_capacity = (underutil_percentage / 100) * underutilized_resource['max_capacity']
                
                if available_capacity > 0:
                    hours_to_move = min(excess_hours, available_capacity)
                    recommendations.append({
                        'type': 'Reassign Tasks',
                        'from': overloaded_resource['resource_name'],
                        'to': underutilized_resource['resource_name'],
                        'hours': hours_to_move,
                        'priority': 'High' if overloaded_resource['workload_percentage'] > 120 else 'Medium'
                    })
    
    elif overloaded and not underutilized:
        for resource in overloaded:
            overload_percentage = resource['workload_percentage'] - 100
            excess_hours = (overload_percentage / 100) * resource['max_capacity']
            recommendations.append({
                'type': 'Hire Additional Resources',
                'resource': resource['resource_name'],
                'reason': f'Overloaded by {resource["workload_percentage"] - 100:.1f}% ({excess_hours:.1f} hours)',
                'priority': 'High' if resource['workload_percentage'] > 120 else 'Medium'
            })
    
    elif underutilized:
        for resource in underutilized:
            underutil_percentage = 100 - resource['workload_percentage']
            available_hours = (underutil_percentage / 100) * resource['max_capacity']
            recommendations.append({
                'type': 'Increase Utilization',
                'resource': resource['resource_name'],
                'available_capacity': f'{100 - resource["workload_percentage"]:.1f}% ({available_hours:.1f} hours)',
                'priority': 'Low'
            })
    
    return recommendations

def export_to_csv(workload_df, analysis):
    """Export analysis to CSV"""
    csv_buffer = io.StringIO()
    workload_df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

def export_to_pdf(workload_df, analysis, recommendations):
    """Export analysis to PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0078D4'),
        spaceAfter=30
    )
    elements.append(Paragraph("Resource Workload Analysis Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Summary
    summary_text = f"""
    <b>Analysis Summary</b><br/>
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
    Total Resources: {len(workload_df)}<br/>
    Overloaded: {len(analysis['overloaded'])}<br/>
    Optimal: {len(analysis['optimal'])}<br/>
    Underutilized: {len(analysis['underutilized'])}
    """
    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Workload table
    table_data = [['Resource', 'Allocated', 'Capacity', 'Workload %', 'Tasks', 'Status']]
    
    for _, row in workload_df.iterrows():
        status = 'Overloaded' if row['Workload %'] > 100 else ('Optimal' if row['Workload %'] >= 70 else 'Underutilized')
        table_data.append([
            row['Resource Name'],
            f"{row['Allocated Hours']:.1f}h",
            f"{row['Capacity Hours']:.1f}h",
            f"{row['Workload %']:.1f}%",
            str(row['Task Count']),
            status
        ])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Recommendations
    if recommendations:
        elements.append(Paragraph("<b>Recommendations</b>", styles['Heading2']))
        for i, rec in enumerate(recommendations[:10], 1):
            rec_text = f"{i}. {rec.get('type', 'N/A')}"
            if 'from' in rec:
                rec_text += f" - Move {rec['hours']:.1f}h from {rec['from']} to {rec['to']}"
            elements.append(Paragraph(rec_text, styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Initialize session state
if 'workload_data' not in st.session_state:
    st.session_state.workload_data = None
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'parser' not in st.session_state:
    st.session_state.parser = None

# Main application
def main():
    # Header
    st.markdown("""
        <h1 style='color: #0078D4; margin-bottom: 10px;'>📊 Resource Management Analyzer</h1>
        <p style='color: #323130; font-size: 16px; margin-bottom: 30px;'>
            Analyze Microsoft Project files to identify workload imbalances and optimize resource allocation
        </p>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📁 Upload MS Project File")
        st.markdown("Supported formats: .xml, .mspdi")
        st.info("💡 To export .mpp to XML: In MS Project, go to File → Save As → select XML Format (*.xml)")
        
        uploaded_file = st.file_uploader(
            "Choose file",
            type=['xml', 'mspdi'],
            help="Upload your Microsoft Project XML file"
        )
        
        if uploaded_file:
            st.success(f"✓ {uploaded_file.name} loaded")
            
            if st.button("🔄 Parse File", use_container_width=True):
                with st.spinner("Parsing MS Project file..."):
                    file_content = uploaded_file.read()
                    parser = MSProjectParser(file_content)
                    
                    if parser.parse():
                        st.session_state.parser = parser
                        st.session_state.workload_data = parser.get_resource_workload_data()
                        st.session_state.analysis = analyze_workload(st.session_state.workload_data)
                        st.success("✓ File parsed successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to parse file")
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
        This tool helps you:
        - Identify overloaded resources (>100%)
        - Find underutilized capacity (<70%)
        - Get workload balancing recommendations
        - Export analysis reports
        """)
    
    # Main content
    if st.session_state.workload_data is None:
        # Welcome screen
        st.info("👆 Upload a Microsoft Project XML file to begin analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #FF4B4B;'>Identify Overload</h3>
                    <p>Detect resources working above 100% capacity</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #107C10;'>Optimize Allocation</h3>
                    <p>Get recommendations for better resource distribution</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
                <div class='metric-card'>
                    <h3 style='color: #0078D4;'>Export Reports</h3>
                    <p>Download analysis as CSV or PDF</p>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Sample Analysis Preview")
        st.markdown("Upload your file to see detailed resource analysis with:")
        st.markdown("- Color-coded workload indicators")
        st.markdown("- Task assignments per resource")
        st.markdown("- Actionable recommendations")
        st.markdown("- Summary statistics")
        
    else:
        # Display analysis
        workload_data = st.session_state.workload_data
        analysis = st.session_state.analysis
        
        # Summary metrics
        st.markdown("### 📊 Summary Dashboard")
        
        # Get project duration info
        project_weeks = workload_data[0]['project_weeks'] if workload_data else 4
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Resources", len(workload_data))
        
        with col2:
            st.metric("Project Duration", f"{project_weeks:.1f} weeks")
        
        with col3:
            st.metric("Overloaded", len(analysis['overloaded']), 
                     delta=f"{len(analysis['overloaded'])}" if len(analysis['overloaded']) > 0 else None,
                     delta_color="inverse")
        
        with col4:
            st.metric("Optimal", len(analysis['optimal']),
                     delta_color="off")
        
        with col5:
            st.metric("Underutilized", len(analysis['underutilized']),
                     delta=f"{len(analysis['underutilized'])}" if len(analysis['underutilized']) > 0 else None,
                     delta_color="normal")
        
        st.markdown("---")
        
        # Personnel search
        st.markdown("### 🔍 Filter by Personnel")
        all_names = [item['resource_name'] for item in workload_data]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("Search by surname or name:", placeholder="e.g., Smith")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            show_all = st.checkbox("Show All", value=True)
        
        # Filter data
        if show_all or not search_term:
            filtered_data = workload_data
        else:
            filtered_data = [item for item in workload_data 
                           if search_term.lower() in item['resource_name'].lower()]
        
        if not filtered_data:
            st.warning("No resources found matching your search.")
        else:
            # Multi-select
            selected_resources = st.multiselect(
                "Select specific resources to analyze:",
                options=[item['resource_name'] for item in filtered_data],
                default=[item['resource_name'] for item in filtered_data]
            )
            
            if selected_resources:
                display_data = [item for item in filtered_data 
                              if item['resource_name'] in selected_resources]
            else:
                display_data = filtered_data
            
            # Workload analysis table
            st.markdown("### 📈 Workload Analysis")
            
            # Prepare dataframe
            df_data = []
            for item in display_data:
                percentage = item['workload_percentage']
                
                # Status indicator
                if percentage > 100:
                    status = "🔴 Overloaded"
                    status_color = "#FF4B4B"
                elif percentage >= 70:
                    status = "🟢 Optimal"
                    status_color = "#107C10"
                else:
                    status = "🟡 Underutilized"
                    status_color = "#FFB900"
                
                df_data.append({
                    'Resource Name': item['resource_name'],
                    'Allocated Hours': item['total_work_hours'],
                    'Capacity Hours': item['max_capacity'],
                    'Workload %': percentage,
                    'Task Count': item['task_count'],
                    'Status': status
                })
            
            df = pd.DataFrame(df_data)
            
            # Color the dataframe
            def highlight_workload(row):
                if row['Workload %'] > 100:
                    return ['background-color: #FFE5E5'] * len(row)
                elif row['Workload %'] < 70:
                    return ['background-color: #FFF4E5'] * len(row)
                else:
                    return ['background-color: #E5F5E5'] * len(row)
            
            styled_df = df.style.apply(highlight_workload, axis=1).format({
                'Allocated Hours': '{:.1f}',
                'Capacity Hours': '{:.1f}',
                'Workload %': '{:.1f}%'
            })
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Detailed task breakdown
            st.markdown("### 📋 Task Breakdown")
            
            for item in display_data:
                with st.expander(f"{item['resource_name']} - {item['workload_percentage']:.1f}% workload"):
                    if item['tasks']:
                        task_df = pd.DataFrame(item['tasks'])
                        st.dataframe(task_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No tasks assigned")
            
            # Recommendations
            st.markdown("### 💡 Recommendations")
            
            recommendations = generate_recommendations(analysis)
            
            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    priority_color = {
                        'High': '#FF4B4B',
                        'Medium': '#FFB900',
                        'Low': '#107C10'
                    }.get(rec.get('priority', 'Low'), '#107C10')
                    
                    if rec['type'] == 'Reassign Tasks':
                        st.markdown(f"""
                        <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                    margin: 10px 0; border-left: 4px solid {priority_color}'>
                            <b>{i}. {rec['type']}</b> 
                            <span style='background-color: {priority_color}; color: white; 
                                         padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                {rec['priority']} Priority
                            </span><br/>
                            Move <b>{rec['hours']:.1f} hours</b> of work from 
                            <b>{rec['from']}</b> to <b>{rec['to']}</b>
                        </div>
                        """, unsafe_allow_html=True)
                    elif rec['type'] == 'Hire Additional Resources':
                        st.markdown(f"""
                        <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                    margin: 10px 0; border-left: 4px solid {priority_color}'>
                            <b>{i}. {rec['type']}</b>
                            <span style='background-color: {priority_color}; color: white; 
                                         padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                {rec['priority']} Priority
                            </span><br/>
                            Consider hiring additional resources to support <b>{rec['resource']}</b><br/>
                            Reason: {rec['reason']}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background-color: white; padding: 15px; border-radius: 8px; 
                                    margin: 10px 0; border-left: 4px solid {priority_color}'>
                            <b>{i}. {rec['type']}</b>
                            <span style='background-color: {priority_color}; color: white; 
                                         padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-left: 10px'>
                                {rec['priority']} Priority
                            </span><br/>
                            <b>{rec['resource']}</b> has {rec['available_capacity']} available capacity
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✓ All resources are optimally allocated!")
            
            # Export options
            st.markdown("### 📥 Export Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                csv_data = export_to_csv(df, analysis)
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                pdf_data = export_to_pdf(df, analysis, recommendations)
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name=f"resource_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Visualization
            st.markdown("### 📊 Workload Distribution")
            
            fig = go.Figure()
            
            # Add bars
            colors_map = []
            for item in display_data:
                percentage = item['workload_percentage']
                if percentage > 100:
                    colors_map.append('#FF4B4B')
                elif percentage >= 70:
                    colors_map.append('#107C10')
                else:
                    colors_map.append('#FFB900')
            
            fig.add_trace(go.Bar(
                x=[item['resource_name'] for item in display_data],
                y=[item['workload_percentage'] for item in display_data],
                marker_color=colors_map,
                text=[f"{item['workload_percentage']:.1f}%" for item in display_data],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Workload: %{y:.1f}%<br><extra></extra>'
            ))
            
            # Add threshold lines
            fig.add_hline(y=100, line_dash="dash", line_color="#FF4B4B", 
                         annotation_text="100% Capacity", annotation_position="right")
            fig.add_hline(y=70, line_dash="dash", line_color="#FFB900", 
                         annotation_text="70% Threshold", annotation_position="right")
            
            fig.update_layout(
                title="Resource Workload Comparison",
                xaxis_title="Resource",
                yaxis_title="Workload Percentage (%)",
                showlegend=False,
                height=500,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(family="Segoe UI, Inter, sans-serif", size=12, color="#323130")
            )
            
            fig.update_xaxis(showgrid=False)
            fig.update_yaxis(showgrid=True, gridcolor='#E5E5E5')
            
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
