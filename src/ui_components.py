
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
        
    card_html = f"""
    <div class="glass animate-fade-in" style="margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex-grow: 1;">
                <p style="color: #A0AEC0; font-size: 0.85rem; margin-bottom: 0.25rem;">
                    {insight['model']} • {insight['type']}
                </p>
                <p style="color: #F8F9FA; font-weight: 500; font-size: 1.05rem; margin-bottom: 0.5rem;">
                    "{insight['original_text']}"
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
        st.write(f"**Variables:** {', '.join(insight.get('variables', []))}")
        
        validation = insight.get('validation', {})
        st.write(f"**Reason:** {validation.get('reason', 'N/A')}")
        
        if 'ground_truth' in validation:
            gt = validation['ground_truth']
            st.json(gt)

def render_correlation_heatmap(corr_matrix):
    """
    Renders a Plotly heatmap for correlations.
    """
    if corr_matrix.empty:
        st.warning("No numeric data for correlations.")
        return
        
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
        font=dict(color="#A0AEC0")
    )
    st.plotly_chart(fig, use_container_width=True)

def render_distribution_plot(df, column):
    """
    Renders a distribution plot (histogram + KDE) for a column.
    """
    fig = px.histogram(
        df, x=column, 
        marginal="box",
        color_discrete_sequence=['#00D9FF']
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#A0AEC0"),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)
