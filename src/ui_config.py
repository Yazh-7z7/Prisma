
# Custom CSS for the applications
CUSTOM_CSS = """
<style>
/* Hide Streamlit default elements */
#MainMenu, footer, header {visibility: hidden;}

/* Base Colors Mapping */
:root {
    --bg-primary: #0A0E17;
    --bg-secondary: #1A1F2E;
    --bg-tertiary: #252A3A;
    --accent-cyan: #00D9FF;
    --accent-purple: #7B61FF;
    --accent-pink: #FF6B9D;
    --status-valid: #10B981;
    --status-unverified: #F59E0B;
    --status-hallucination: #EF4444;
    --text-primary: #F8F9FA;
    --text-secondary: #A0AEC0;
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb {
    background: linear-gradient(135deg, #00D9FF, #7B61FF);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
    background: #00D9FF;
}

/* Glassmorphism utility */
.glass {
    background: rgba(26, 31, 46, 0.7);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.05);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    border-radius: 1rem;
    padding: 1.5rem;
}

/* Gradient text utility */
.gradient-text {
    background: linear-gradient(135deg, #00D9FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700;
}

/* Button styles - Overriding Streamlit buttons */
div.stButton > button {
    background: linear-gradient(135deg, #00D9FF, #7B61FF);
    color: white;
    border: none;
    border-radius: 0.75rem;
    padding: 0.6rem 1.5rem;
    font-weight: 600;
    transition: all 200ms ease;
    box-shadow: 0 4px 16px rgba(0,217,255,0.25);
    width: 100%;
}
div.stButton > button:hover {
    transform: scale(1.02);
    box-shadow: 0 8px 24px rgba(0,217,255,0.35);
    color: white;
}
div.stButton > button:active {
    transform: scale(0.98);
}

/* Secondary/Outline Button (Simulated via specific class or context if possible, 
   but Streamlit makes targeting specific buttons hard without keys. 
   We'll assume default buttons are primary) */

/* File uploader */
.stFileUploader section {
    border: 2px dashed #00D9FF;
    border-radius: 1rem;
    padding: 2rem;
    background: rgba(0,217,255,0.05);
    transition: all 300ms ease;
}
.stFileUploader section:hover {
    border-color: #7B61FF;
    background: rgba(123,97,255,0.05);
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: rgba(26, 31, 46, 0.8);
    backdrop-filter: blur(20px);
    padding: 1rem;
    border-radius: 1rem;
    border: 1px solid rgba(255,255,255,0.05);
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
div[data-testid="stMetric"] label {
    color: #A0AEC0;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #F8F9FA;
    font-weight: 700;
}

/* Dataframe */
div.stDataFrame {
    border-radius: 1rem;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.05);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 1rem;
    background: transparent;
    padding-bottom: 5px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
    color: #A0AEC0;
    font-weight: 500;
    border: 1px solid transparent;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,217,255,0.1), rgba(123,97,255,0.1));
    color: #F8F9FA;
    border-bottom: 2px solid #00D9FF;
    border-color: rgba(0,217,255,0.2);
}

/* Expander/Accordion */
.streamlit-expanderHeader {
    background-color: rgba(255,255,255,0.03);
    border-radius: 0.5rem;
    color: #F8F9FA;
}

/* Card Badge Styles */
.badge {
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
}
.badge-valid {
    background: rgba(16,185,129,0.2);
    color: #10B981;
    border: 1px solid rgba(16,185,129,0.3);
}
.badge-hallucination {
    background: rgba(239,68,68,0.2);
    color: #EF4444;
    border: 1px solid rgba(239,68,68,0.3);
}
.badge-unverified {
    background: rgba(245,158,11,0.2);
    color: #F59E0B;
    border: 1px solid rgba(245,158,11,0.3);
}

/* Animations */
@keyframes fadeIn {
    from {opacity: 0; transform: translateY(10px);}
    to {opacity: 1; transform: translateY(0);}
}
.animate-fade-in {
    animation: fadeIn 0.5s ease-out forwards;
}

</style>
"""
