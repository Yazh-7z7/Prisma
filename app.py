
import streamlit as st
import pandas as pd
import os
import time
from src.ui_config import CUSTOM_CSS
from src.ui_components import render_metric_card, render_insight_card, render_correlation_heatmap, render_distribution_plot
from src.statistical_engine import StatisticalEngine
from src.llm_generator import LLMGenerator
from src.insight_parser import InsightParser
from src.validator import Validator
from src.hallucination_detector import HallucinationDetector
from src.report_generator import ReportGenerator
import yaml
import plotly.express as px

# Page Config
st.set_page_config(
    page_title="Hallucination Detector",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Load Configuration
@st.cache_resource
def load_config():
    # Only load config once per session
    if not os.path.exists("config/config.yaml"):
        st.error("Config file not found!")
        return {}
    with open("config/config.yaml", 'r') as stream:
        return yaml.safe_load(stream)

config = load_config()

# Initialize Session State
if 'data' not in st.session_state:
    st.session_state.data = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'insights' not in st.session_state:
    st.session_state.insights = None
if 'validation_results' not in st.session_state:
    st.session_state.validation_results = None

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🔍 Hallucination Detector")
    st.markdown("AI Insight Validation System")
    
    st.markdown("---")
    
    # 1. Data Upload
    st.subheader("📁 Data Configuration")
    uploaded_file = st.file_uploader("Upload Dataset", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.session_state.data = df
            st.success(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        except Exception as e:
            st.error(f"Error loading file: {e}")

    st.markdown("---")

    # 2. API Configuration
    with st.expander("🔑 API Keys", expanded=False):
        anthropic_key = st.text_input("Anthropic API Key", type="password", value=config.get('llm', {}).get('api_keys', {}).get('anthropic', ''))
        openai_key = st.text_input("OpenAI API Key", type="password", value=config.get('llm', {}).get('api_keys', {}).get('openai', ''))
        
        if st.button("Save Keys"):
            # Update config in memory (for this session)
            if 'llm' not in config: config['llm'] = {}
            if 'api_keys' not in config['llm']: config['llm']['api_keys'] = {}
            
            config['llm']['api_keys']['anthropic'] = anthropic_key
            config['llm']['api_keys']['openai'] = openai_key
            st.toast("API Keys saved for session!", icon="✅")

    # 3. Model Selection
    st.subheader("🤖 Model Selection")
    
    selected_provider = st.radio(
        "Select Provider",
        ["Ollama (Local)", "Anthropic (Claude)", "OpenAI (GPT)"],
        index=0
    )
    
    model_name = "gemma:2b"
    provider = "ollama"
    
    if "Ollama" in selected_provider:
        provider = "ollama"
        model_name = st.text_input("Model Name", value="gemma:2b")
    elif "Anthropic" in selected_provider:
        provider = "anthropic"
        model_name = st.selectbox("Model", ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"])
    elif "OpenAI" in selected_provider:
        provider = "openai"
        model_name = st.selectbox("Model", ["gpt-4-turbo", "gpt-3.5-turbo"])

    # 4. Analysis Settings
    st.subheader("⚙️ Settings")
    num_insights = st.slider("Number of Insights", 5, 20, 10)
    
    # Run Button
    run_btn = st.button("🚀 Run Analysis", disabled=(st.session_state.data is None))


# --- MAIN CONTENT ---

# Tabs
tab_dashboard, tab_data, tab_truth, tab_insights, tab_validation, tab_reports = st.tabs([
    "📊 Dashboard", "📈 Data Preview", "🔍 Ground Truth", "💡 Insights", "✅ Validation", "📄 Reports"
])

# --- LOGIC HANDLERS ---
if run_btn and st.session_state.data is not None:
    with st.spinner("Running Analysis Pipeline..."):
        # 1. Statistical Analysis
        stat_engine = StatisticalEngine(config)
        ground_truth = stat_engine.analyze_dataset(st.session_state.data)
        st.session_state.analysis_results = ground_truth
        
        # 2. Generate Insights
        llm_gen = LLMGenerator(config)
        # Verify keys are set if needed
        if provider != 'ollama':
            # Temporary override for this instance
            if provider == 'anthropic':
                llm_gen.anthropic_key = config['llm']['api_keys']['anthropic']
            elif provider == 'openai':
                llm_gen.openai_key = config['llm']['api_keys']['openai']

        # Convert ground truth to string for the prompt
        import json
        summary_str = json.dumps(ground_truth, indent=2, default=str)

        try:
            raw_response = llm_gen.generate_insights(
                dataset_summary=summary_str,
                model_provider=provider, 
                model_name=model_name
            )
        except Exception as e:
            st.error(f"Failed to generate insights: {e}")
            st.stop()
            
        # 3. Parse Insights
        parser = InsightParser()
        parsed_claims = parser.parse_insights(raw_response)
        st.session_state.insights = parsed_claims
        
        # 4. Validate
        validator = Validator(config)
        validation_results = validator.validate_claims(parsed_claims, ground_truth, st.session_state.data.columns)
        st.session_state.validation_results = validation_results
        
        st.success("Analysis Complete!")


# --- TABS CONTENT ---

with tab_dashboard:
    st.markdown("<h1 class='gradient-text'>Hallucination Detection Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("Validate AI-generated insights with statistical ground truth.")
    
    if st.session_state.validation_results:
        metrics_calc = HallucinationDetector(config)
        metrics = metrics_calc.calculate_metrics(st.session_state.validation_results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            render_metric_card("Hallucination Rate", f"{metrics.get('hallucination_rate', 0):.1f}%")
        with col2:
            render_metric_card("Validity Score", f"{metrics.get('validity_score', 0):.1f}%")
        with col3:
            render_metric_card("Total Claims", metrics.get('total_claims', 0))
        with col4:
            render_metric_card("Verified Claims", metrics.get('verified_claims', 0))
            
        st.markdown("### Recent Activity")
        st.info("Analysis run successfully. Check other tabs for details.")
        
    else:
        st.info("Upload a dataset and click 'Run Analysis' to see the dashboard.")

with tab_data:
    if st.session_state.data is not None:
        st.subheader("Dataset Overview")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rows", st.session_state.data.shape[0])
        with col2:
            st.metric("Columns", st.session_state.data.shape[1])
        with col3:
            st.metric("Missing Values", st.session_state.data.isna().sum().sum())
            
        st.dataframe(st.session_state.data, use_container_width=True)
        
        st.subheader("Column Statistics")
        selected_col = st.selectbox("Select Column", st.session_state.data.columns)
        if selected_col:
            col_stats = st.session_state.data[selected_col].describe()
            st.write(col_stats)
            
            if pd.api.types.is_numeric_dtype(st.session_state.data[selected_col]):
                 render_distribution_plot(st.session_state.data, selected_col)
    else:
        st.warning("Please upload a dataset.")

with tab_truth:
    if st.session_state.data is not None:
        st.subheader("Ground Truth Analysis")
        
        # Correlation Matrix
        numeric_df = st.session_state.data.select_dtypes(include=['float64', 'int64'])
        if not numeric_df.empty:
            st.markdown("### Correlation Matrix")
            corr = numeric_df.corr()
            render_correlation_heatmap(corr)
        
        # Show results from Stat Engine if available
        if st.session_state.analysis_results:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Group Differences")
                diffs = st.session_state.analysis_results.get('group_differences', [])
                if diffs:
                    st.dataframe(pd.DataFrame(diffs))
                else:
                    st.info("No significant group differences found.")
            
            with col2:
                st.markdown("### Categorical Associations")
                assocs = st.session_state.analysis_results.get('categorical_associations', [])
                if assocs:
                    st.dataframe(pd.DataFrame(assocs))
                else:
                    st.info("No significant categorical associations found.")
    else:
        st.warning("Please upload a dataset.")

with tab_insights:
    if st.session_state.validation_results:
        st.subheader("Generated Insights & Validation")
        
        filter_status = st.multiselect(
            "Filter by Status", 
            ["VALID", "UNVERIFIED", "HALLUCINATION_RELATIONSHIP", "HALLUCINATION_DIRECTION", "HALLUCINATION_STRENGTH"],
            default=["VALID", "UNVERIFIED", "HALLUCINATION_RELATIONSHIP"]
        )
        
        count = 0
        for insight_data in st.session_state.validation_results:
            # The structure returned by Validator.validate_claims is list of dicts.
            # Each dict contains: 'claim' (original dict), 'extracted_vars', 'status', 'reason'.
            
            status = insight_data.get('status', 'UNVERIFIED')
            # Check for partial match in filter (handles subtypes of hallucination)
            if any(f in status for f in filter_status) or (not filter_status):
                
                # We need to construct a clean object for the renderer
                display_obj = insight_data['claim'].copy()
                display_obj['validation'] = {
                    'status': status, 
                    'reason': insight_data.get('reason'),
                    'ground_truth': insight_data.get('ground_truth')
                }
                display_obj['variables'] = insight_data.get('extracted_vars', [])
                display_obj['model'] = model_name
                
                render_insight_card(display_obj)
                count += 1
        
        if count == 0:
            st.info("No insights match the selected filters.")
    else:
        st.info("Run analysis to generate insights.")

with tab_validation:
    if st.session_state.validation_results:
        st.subheader("Validation Breakdown")
        
        # Create a DataFrame for easy visualization
        val_data = []
        for v in st.session_state.validation_results:
            val_data.append({
                "Status": v.get('status', 'UNKNOWN'),
                "Confidence": v['claim'].get('confidence_score', 0),
                "Type": v['claim'].get('type', 'Unknown'),
                "Reason": v.get('reason', '')
            })
        val_df = pd.DataFrame(val_data)
        
        if not val_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Status Distribution")
                status_counts = val_df['Status'].value_counts()
                fig = px.pie(values=status_counts.values, names=status_counts.index, hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                st.markdown("### Confidence vs Validation")
                fig2 = px.box(val_df, x="Status", y="Confidence", color="Status")
                st.plotly_chart(fig2, use_container_width=True)
                
            st.markdown("### Detailed Validation Table")
            st.dataframe(val_df, use_container_width=True)
        else:
            st.warning("No validation data available.")
            
    else:
        st.info("Run analysis to see validation results.")

with tab_reports:
    if st.session_state.validation_results:
        st.subheader("Report Generation")
        
        default_name = f"report_{int(time.time())}"
        if uploaded_file:
            default_name = f"{uploaded_file.name}_{int(time.time())}"
            
        report_name = st.text_input("Report Name", default_name)
        
        if st.button("Generate Report"):
            report_gen = ReportGenerator(config)
            
            # Metrics calculation again for report
            metrics_calc = HallucinationDetector(config)
            metrics = metrics_calc.calculate_metrics(st.session_state.validation_results)
            
            # Use internal method or expose one
            # We recreate usage from report_generator.py logic
            report_gen.generate_reports(
                st.session_state.validation_results, 
                metrics, 
                uploaded_file.name if uploaded_file else "dataset", 
                model_name
            )
            st.success(f"Report '{report_name}' generated successfully in results/reports/")
            st.balloons()
            
        st.markdown("### Export Options")
        
        import json
        json_str = json.dumps(st.session_state.validation_results, default=str)
        
        st.download_button(
            "Download Insights (JSON)",
            data=json_str,
            file_name="insights.json",
            mime="application/json"
        )
    else:
        st.info("Run analysis to enable reporting.")
