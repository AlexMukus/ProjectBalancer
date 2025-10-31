"""
Fluent UI Theme Components
Бекап текущего дизайна Microsoft Fluent UI
"""

def get_fluent_ui_css():
    """Возвращает CSS стили для темы Fluent UI"""
    return """
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
    """
