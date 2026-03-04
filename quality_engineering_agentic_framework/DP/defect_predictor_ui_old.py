import streamlit as st
import requests
import plotly.graph_objects as go

# Lambda URL
LAMBDA_URL = 'https://kmqbp6s6unfyfbsyjepsqa5yx40bhbko.lambda-url.eu-north-1.on.aws/'

def create_defect_probability_chart(probability):
    """Create a professional donut chart for defect probability"""
    # Determine color based on probability
    if probability < 30:
        color = '#10b981'  # Green
    elif probability < 50:
        color = '#f59e0b'  # Amber
    elif probability < 70:
        color = '#ea580c'  # Orange
    else:
        color = '#dc2626'  # Red
    
    fig = go.Figure(data=[go.Pie(
        values=[probability, 100-probability],
        labels=['Defect Risk', 'Safe'],
        hole=0.6,
        marker=dict(colors=[color, '#f3f4f6']),
        textinfo='none',
        hoverinfo='label+percent',
        showlegend=False
    )])
    
    fig.update_layout(
        annotations=[dict(text=f'{probability}%', x=0.5, y=0.5, font_size=40, showarrow=False)],
        height=280,
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def display_results(data, story_key=None):
    """Display prediction results with clean professional styling"""
    
    # Story header
    if story_key:
        st.markdown(f"### {story_key}")
        st.markdown(f"**{data.get('story_title', 'Untitled')}**")
    
    st.markdown("---")
    
    # Top row - 3 metrics boxes (equal size, consistent styling)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Predicted Bugs**")
        st.markdown(f"<h2>{data.get('predicted_bugs', 0)}</h2>", unsafe_allow_html=True)
    
    with col2:
        risk = data.get('risk_level', 'UNKNOWN')
        st.markdown("**Risk Level**")
        st.markdown(f"<h2 style='color: {'#dc2626' if risk == 'CRITICAL' else '#ea580c' if risk == 'HIGH' else '#f59e0b' if risk == 'MEDIUM' else '#10b981'};'>{risk}</h2>", unsafe_allow_html=True)
    
    with col3:
        # Calculate regression score
        regression_score = round(100 - abs(data.get('defect_probability', 50) - 50), 1)
        st.markdown("**Regression Score**")
        st.markdown(f"<h2>{regression_score}%</h2>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Center: Defect Probability Chart
    st.markdown("**Defect Probability**")
    
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        fig = create_defect_probability_chart(data.get('defect_probability', 0))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Feature Importance (collapsed by default)
    with st.expander("📊 Feature Importance", expanded=False):
        for feature in data.get('feature_importance', []):
            st.text(f"{feature['factor']}: {feature['importance']}")

def render_jira_mode():
    """JIRA story key input mode"""
    st.subheader("Fetch from JIRA")
    
    story_key = st.text_input("JIRA Story Key", placeholder="e.g., SCRUM-1325")
    
    if st.button("Run AI Prediction", type="primary"):
        if not story_key:
            st.error("Please enter a JIRA story key")
            return
            
        with st.spinner("Fetching story from JIRA and analyzing..."):
            try:
                response = requests.post(
                    LAMBDA_URL,
                    json={"jira_story_key": story_key},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    display_results(result, story_key)
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
                    
            except Exception as e:
                st.error(f"Failed to fetch: {str(e)}")

def render_custom_mode():
    """Custom parameters input mode"""
    st.subheader("Custom Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        story_title = st.text_input("Story Title", "My Story")
        component = st.selectbox("Component", [
            "Email Service", "Frontend Dashboard", "API Gateway",
            "Billing & Invoicing", "User Authentication", "Payment Gateway"
        ])
        story_points = st.number_input("Story Points", 1, 21, 5)
        complexity = st.slider("Complexity (1-5)", 1, 5, 3)
        dependencies = st.number_input("Dependencies", 0, 10, 2)
        developer_experience = st.slider("Developer Experience (years)", 1.0, 10.0, 4.0, 0.5)
    
    with col2:
        risk_level = st.selectbox("Risk Level", ["low", "medium", "high", "critical"])
        previous_bugs = st.number_input("Previous Bugs in Component", 0, 50, 5)
        test_coverage = st.slider("Test Coverage (%)", 0, 100, 75)
        code_churn = st.number_input("Code Churn (lines)", 0, 5000, 1000)
        team_size = st.number_input("Team Size", 1, 20, 5)
        
    col3, col4 = st.columns(2)
    with col3:
        is_new_feature = st.checkbox("New Feature")
    with col4:
        has_external_dep = st.checkbox("External Dependency")
    
    if st.button("Run AI Prediction", type="primary", key="custom_predict"):
        with st.spinner("Analyzing..."):
            try:
                response = requests.post(
                    LAMBDA_URL,
                    json={
                        "story_mode": True,
                        "story_title": story_title,
                        "component": component,
                        "story_points": story_points,
                        "complexity": complexity,
                        "dependencies": dependencies,
                        "developer_experience": developer_experience,
                        "risk_level": risk_level,
                        "previous_bugs_in_component": previous_bugs,
                        "test_coverage": test_coverage,
                        "code_churn_lines": code_churn,
                        "team_size": team_size,
                        "is_new_feature": 1 if is_new_feature else 0,
                        "has_external_dependency": 1 if has_external_dep else 0
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    display_results(result)
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
                    
            except Exception as e:
                st.error(f"Failed: {str(e)}")

def render_defect_predictor_tab():
    """Main DefectPredictor tab"""
    st.header("DefectPredictor - AI-Powered Bug Prediction")
    st.write("Predict bugs at story-level with 88.3% accuracy using ML")
    
    # Mode selection
    mode = st.radio("Input Mode", ["JIRA Story Key", "Custom Parameters"], horizontal=True)
    
    if mode == "JIRA Story Key":
        render_jira_mode()
    else:
        render_custom_mode()

