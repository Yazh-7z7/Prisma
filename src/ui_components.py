import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff

def render_metric_card(label, value, delta=None, color="default"):
    """
    Renders a styled metric card.
    """
    st.metric(label=label, value=value, delta=delta)

def render_insight_card(insight):
    """
    Renders a single insight card with status badge.
    FIXED: Added .get() to prevent KeyError
    """
    status = insight.get('validation', {}).get('status', 'UNVERIFIED')
    confidence = insight.get('confidence_score', 0) * 100
    
    badge_class = "badge-unverified"
    icon = "⚠️"
    if status == "VALID":
        badge_class = "badge-valid"
        icon = "✅"
    elif "HALLUCINATION" in status:
        badge_class = "badge-hallucination"
        icon = "❌"
    
    # FIXED: Use .get() with defaults to prevent KeyError
    model_name = insight.get('model', 'Unknown Model')
    insight_type = insight.get('type', 'Unknown Type')
    original_text = insight.get('original_text', 'No text available')
    
    card_html = f"""
    <div class="glass animate-fade-in" style="margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex-grow: 1;">
                <p style="color: #A0AEC0; font-size: 0.85rem; margin-bottom: 0.25rem;">
                    {model_name} • {insight_type}
                </p>
                <p style="color: #F8F9FA; font-weight: 500; font-size: 1.05rem; margin-bottom: 0.5rem;">
                    "{original_text}"
                </p>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <span class="badge {badge_class}">{icon} {status}</span>
                    <span style="color: #A0AEC0; font-size: 0.8rem; align-self: center;">
                        Conf: {confidence:.0f}%
                    </span>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Detail expander
    with st.expander("View Details & Ground Truth"):
        variables = insight.get('variables', [])
        if variables:
            st.write(f"**Variables:** {', '.join(variables)}")
        else:
            st.write("**Variables:** None extracted")
        
        validation = insight.get('validation', {})
        reason = validation.get('reason', 'No reason provided')
        st.write(f"**Reason:** {reason}")
        
        if 'ground_truth' in validation and validation['ground_truth']:
            st.markdown("**Ground Truth:**")
            st.json(validation['ground_truth'])
        else:
            st.info("No ground truth data available")

def render_correlation_heatmap(corr_matrix):
    """
    Renders a Plotly heatmap for correlations.
    FIXED: Added better validation and error handling
    """
    # Validate input
    if corr_matrix is None:
        st.warning("No correlation matrix provided.")
        return
        
    if corr_matrix.empty:
        st.warning("No numeric data for correlations.")
        return
    
    # Check if matrix has enough data
    if corr_matrix.shape[0] < 2:
        st.warning("Need at least 2 numeric columns for correlation matrix.")
        return
    
    # Check for NaN values
    if corr_matrix.isna().all().all():
        st.warning("Correlation matrix contains only NaN values.")
        return
    
    try:
        fig = px.imshow(
            corr_matrix,
            text_auto=True,
            aspect="auto",
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#A0AEC0"),
            title="Correlation Heatmap"
        )
        st.plotly_chart(fig, use_container_width=True)
    except ValueError as e:
        st.error(f"Could not render correlation heatmap: Invalid data format. {str(e)}")
    except Exception as e:
        st.error(f"Could not render correlation heatmap: {str(e)}")

def render_distribution_plot(df, column):
    """
    Renders a distribution plot (histogram + KDE) for a column.
    FIXED: Added validation and error handling
    """
    # Validate inputs
    if df is None or df.empty:
        st.warning("No data available for plotting.")
        return
    
    if column not in df.columns:
        st.error(f"Column '{column}' not found in dataframe.")
        return
    
    # Check if column has any valid data
    if df[column].isna().all():
        st.warning(f"Column '{column}' contains only missing values.")
        return
    
    # Check if column is numeric
    if not pd.api.types.is_numeric_dtype(df[column]):
        st.warning(f"Column '{column}' is not numeric. Cannot create distribution plot.")
        return
    
    try:
        fig = px.histogram(
            df, x=column, 
            marginal="box",
            color_discrete_sequence=['#00D9FF'],
            title=f"Distribution of {column}"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#A0AEC0"),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Could not render distribution plot: {str(e)}")

def render_error_message(error_title, error_details, show_trace=False):
    """
    Renders a styled error message.
    NEW: Helper function for consistent error display
    """
    st.error(f"**{error_title}**")
    
    with st.expander("Error Details"):
        st.write(error_details)
        
        if show_trace:
            import traceback
            st.code(traceback.format_exc())

def render_info_box(title, content, icon="ℹ️"):
    """
    Renders a styled info box.
    NEW: Helper function for consistent info display
    """
    st.markdown(f"""
    <div class="glass" style="margin: 1rem 0;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.5rem;">{icon}</span>
            <div>
                <p style="color: #F8F9FA; font-weight: 600; margin: 0;">{title}</p>
                <p style="color: #A0AEC0; margin: 0.5rem 0 0 0;">{content}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
