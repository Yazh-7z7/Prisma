import streamlit as st
import pandas as pd
import subprocess
import time

# -----------------------------
# Helper function: Query Ollama
# -----------------------------
def query_ollama(prompt: str, model: str = "gemma3:4b"):
    """Run a local Ollama model with a given prompt and return output."""
    command = ["ollama", "run", model]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    output, error = process.communicate(input=prompt)
    if error and error.strip():
        print("⚠️ Ollama error:", error)
    return output.strip()

# -----------------------------
# Streamlit Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Prisma – AI-Powered Insight Generator",
    page_icon="🔷",
    layout="wide"
)

# Modern 2025 CSS with Purple Theme & Flowing Background
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
.stButton>button {
    transition: transform 0.18s cubic-bezier(.4, 2,.3,.8), box-shadow 0.18s, background 0.4s;
    position: relative;
    overflow: hidden;
    outline: none;
}
.stButton>button:active {
    transform: scale(0.96);
    box-shadow: 0 2px 12px rgba(139,92,246,0.18);
    background: linear-gradient(135deg, #432768 0%, #3c237a 100%);
}
.stButton>button::after {
    content:'';
    position:absolute; left:50%; top:50%; transform: translate(-50%,-50%) scale(0);
    width:120%; height:120%;
    border-radius:999px;
    background: rgba(139,92,246,0.16);
    animation: ripple 0.5s;
    pointer-events: none;
}
.stButton>button:active::after {
    animation: ripple 0.4s;
    transform: translate(-50%,-50%) scale(1);
}

@keyframes ripple {
    from { opacity: 1; transform: translate(-50%,-50%) scale(0.3);}
    to   { opacity: 0; transform: translate(-50%,-50%) scale(1.2);}
}
.stFileUploader, .stFileUploader section {
    transition: box-shadow 0.35s, transform 0.35s;
}
.stFileUploader:hover {
    box-shadow: 0 12px 30px rgba(139,92,246,0.18), 0 0 12px 2px #8b5cf6;
    transform: scale(1.03);
}
.stFileUploader:active {
    box-shadow: 0 4px 18px rgba(139,92,246,0.14);
    transform: scale(0.98);
}
.stSelectbox>div>div>div {
    transition: box-shadow 0.3s, border 0.2s, transform 0.2s;
}
.stSelectbox>div>div>div:hover {
    box-shadow: 0 6px 24px rgba(139,92,246,0.18);
    transform: scale(1.015);
}
.stSelectbox>div>div>div:active {
    box-shadow: 0 2px 8px #a78bfa;
    transform: scale(0.97);
}
.insights-card {
    transition: box-shadow 0.35s, border 0.27s, transform 0.37s;
}
.insights-card:hover {
    box-shadow: 0 32px 112px rgba(139,92,246,0.12) !important;
    border-color: #a78bfa !important;
    transform: scale(1.012);
}
.insights-card:active {
    box-shadow: 0 8px 32px #c4b5fd;
    transform: scale(0.988);
}
.stTextInput>div>div>input {
    transition: box-shadow 0.29s, border 0.22s, transform 0.19s;
}
.stTextInput>div>div>input:focus {
    box-shadow: 0 0 0 7px rgba(139,92,246,0.27), 0 4px 16px #a78bfa;
    transform: scale(1.03);
}
.stTextInput>div>div>input:active {
    box-shadow: 0 0 0 6px #c4b5fd;
    transform: scale(0.97);
}
.stButton > button:active,
.stFileUploader:active,
.insights-card:active,
.stSelectbox>div>div>div:active,
.stTextInput>div>div>input:active {
    animation: clickPulse 0.19s;
}
@keyframes clickPulse {
    0% { transform: scale(1.02);}
    50% { transform: scale(0.96);}
    100% { transform: scale(1);}
}

/* Global Styles */
:root {
    --primary-purple: #8b5cf6;
    --secondary-purple: #a78bfa;
    --accent-purple: #c4b5fd;
    --dark-bg: #000000;
    --card-bg: #0a0a0f;
}

/* Flowing Black Background with Purple Waves */
.stApp {
    background: #000000;
    position: relative;
    overflow-x: hidden;
}

.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0;
    width: 200%; height: 200%;
    pointer-events: none;
    z-index: 0;
    background:
        radial-gradient(circle at 30% 60%, rgba(64,64,64,0.15) 0%, transparent 60%),
        radial-gradient(circle at 80% 50%, rgba(32,32,32,0.10) 0%, transparent 55%),
        linear-gradient(140deg, rgba(8,8,8,0.92) 0%, rgba(22,22,22,0.60) 100%);
    animation: flowingBlack 18s ease-in-out infinite;
}

@keyframes flowingBlack {
    0%, 100% {
        transform: scale(1) translateX(0vw) translateY(0vw);
        filter: brightness(1);
    }
    33% {
        transform: scale(1.03) translateX(-2vw) translateY(1vw);
        filter: brightness(1.07);
    }
    66% {
        transform: scale(1.01) translateX(2vw) translateY(-1vw);
        filter: brightness(0.93);
    }
}

@keyframes flowingBackground {
    0%, 100% {
        transform: translate(0, 0) rotate(0deg);
    }
    33% {
        transform: translate(-10%, 5%) rotate(2deg);
    }
    66% {
        transform: translate(5%, -10%) rotate(-2deg);
    }
}

.stApp > div {
    position: relative;
    z-index: 1;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #8b5cf6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
}

p, div, span, label {
    font-family: 'Inter', sans-serif !important;
    color: #e2e8f0;
}

/* Logo Styling */
.prisma-logo {
    width: 60px;
    height: 60px;
    display: inline-block;
    vertical-align: middle;
    margin-right: 15px;
    filter: drop-shadow(0 0 20px rgba(139, 92, 246, 0.6));
    animation: logoFloat 3s ease-in-out infinite;
}

@keyframes logoFloat {
    0%, 100% {
        transform: translateY(0px);
    }
    50% {
        transform: translateY(-10px);
    }
}

/* Header Animation */
.main-header {
    animation: slideDown 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    margin-bottom: 3rem;
    text-align: left;
}

@keyframes slideDown {
    from {
        opacity: 0;
        transform: translateY(-30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.header-title {
    display: flex;
    align-items: center;
    margin-bottom: 1rem;
}

/* Enhanced File Uploader */
.stFileUploader {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(0, 0, 0, 0.6) 100%);
    border: 2px solid transparent;
    background-clip: padding-box;
    border-radius: 24px;
    padding: 3rem;
    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    animation: fadeIn 0.6s ease-out 0.2s both;
    position: relative;
    overflow: hidden;
}

.stFileUploader::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 24px;
    padding: 2px;
    background: linear-gradient(135deg, #8b5cf6, #a78bfa, #c4b5fd);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity: 0.4;
    transition: opacity 0.5s;
}

.stFileUploader:hover::before {
    opacity: 1;
}

.stFileUploader:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 60px rgba(139, 92, 246, 0.4);
}

.stFileUploader section {
    border: none !important;
}

.stFileUploader [data-testid="stFileUploaderDropzone"] {
    background: transparent !important;
    border: 2px dashed rgba(139, 92, 246, 0.5) !important;
    border-radius: 16px;
    transition: all 0.3s;
}

.stFileUploader [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #a78bfa !important;
    background: rgba(139, 92, 246, 0.05) !important;
}

.stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] {
    color: #c4b5fd !important;
    font-weight: 600;
    font-size: 1.1rem;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Button Styling */
.stButton>button {
    background: linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%);
    color: white;
    border: none;
    border-radius: 16px;
    padding: 0.9rem 2.5rem;
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.5px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4);
    position: relative;
    overflow: hidden;
}

.stButton>button:before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
    transition: left 0.5s;
}

.stButton>button:hover:before {
    left: 100%;
}

.stButton>button:hover {
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 12px 35px rgba(139, 92, 246, 0.6);
}

.stButton>button:active {
    transform: translateY(-1px) scale(0.98);
}

/* Card Styling */
.insights-card {
    background: linear-gradient(135deg, rgba(10, 10, 15, 0.98) 0%, rgba(20, 10, 30, 0.95) 100%);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 28px;
    padding: 2.5rem;
    margin-top: 2rem;
    box-shadow: 0 15px 50px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(139, 92, 246, 0.2);
    backdrop-filter: blur(20px);
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    animation: slideUp 0.6s ease-out both;
    position: relative;
    overflow: hidden;
}

.insights-card:before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #8b5cf6, #a78bfa, #c4b5fd, #a78bfa, #8b5cf6);
    background-size: 200% 100%;
    opacity: 0;
    transition: opacity 0.3s;
    animation: gradientMove 3s linear infinite;
}

@keyframes gradientMove {
    0% {
        background-position: 0% 0%;
    }
    100% {
        background-position: 200% 0%;
    }
}

.insights-card:hover:before {
    opacity: 1;
}

.insights-card:hover {
    transform: translateY(-8px);
    border-color: rgba(139, 92, 246, 0.5);
    box-shadow: 0 25px 70px rgba(139, 92, 246, 0.4), 0 0 0 1px rgba(139, 92, 246, 0.3);
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(40px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Dataframe Styling */
.stDataFrame {
    animation: fadeIn 0.6s ease-out 0.4s both;
}

.stDataFrame div[data-testid="stDataFrame"] {
    background: rgba(10, 10, 15, 0.9);
    border-radius: 20px;
    border: 1px solid rgba(139, 92, 246, 0.3);
    overflow: hidden;
}

/* Insights Content */
.insights-content {
    color: #e2e8f0;
    line-height: 1.9;
    font-size: 1.05rem;
    white-space: pre-wrap;
    animation: fadeIn 0.8s ease-out;
    padding: 1.5rem;
    background: rgba(139, 92, 246, 0.08);
    border-radius: 16px;
    border-left: 4px solid var(--primary-purple);
}

/* Enhanced Text Input */
.stTextInput>div>div>input {
    background: linear-gradient(135deg, rgba(10, 10, 15, 0.9) 0%, rgba(20, 10, 30, 0.8) 100%);
    border: 2px solid rgba(139, 92, 246, 0.4);
    border-radius: 16px;
    color: white;
    padding: 1rem 1.5rem;
    font-size: 1.05rem;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.stTextInput>div>div>input:focus {
    border-color: var(--primary-purple);
    box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.25), 0 8px 25px rgba(139, 92, 246, 0.3);
    outline: none;
    transform: translateY(-2px);
}

.stTextInput>div>div>input::placeholder {
    color: #a78bfa;
    opacity: 0.6;
}

/* Selectbox */
.stSelectbox>div>div>div {
    background: linear-gradient(135deg, rgba(10, 10, 15, 0.9) 0%, rgba(20, 10, 30, 0.8) 100%);
    border: 2px solid rgba(139, 92, 246, 0.4);
    border-radius: 16px;
    color: white;
    transition: all 0.3s;
}

.stSelectbox>div>div>div:hover {
    border-color: var(--primary-purple);
    box-shadow: 0 4px 15px rgba(139, 92, 246, 0.2);
}

/* Success/Info/Warning Messages */
.stSuccess, .stInfo, .stWarning {
    background: rgba(139, 92, 246, 0.15);
    border-left: 5px solid var(--primary-purple);
    border-radius: 16px;
    padding: 1.2rem;
    animation: slideIn 0.4s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(-30px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

/* Spinner */
.stSpinner > div {
    border-top-color: var(--primary-purple) !important;
}

/* Chat Message */
.chat-message {
    animation: messageSlide 0.5s ease-out;
    margin-bottom: 1.5rem;
    padding: 1.5rem;
    border-radius: 16px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.2);
    transition: all 0.3s;
}

.chat-message:hover {
    background: rgba(139, 92, 246, 0.12);
    border-color: rgba(139, 92, 246, 0.4);
    transform: translateX(5px);
}


@keyframes messageSlide {
    from {
        opacity: 0;
        transform: translateX(-30px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

/* Glow Effect */
.glow-text {
    text-shadow: 0 0 30px rgba(139, 92, 246, 0.6), 0 0 60px rgba(139, 92, 246, 0.3);
}

/* Pulse Animation */
@keyframes pulse {
    0%, 100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.8;
        transform: scale(1.02);
    }
}

/* Scrollbar */
::-webkit-scrollbar {
 width: 12px;
}


::-webkit-scrollbar-track {
 background: #000000;
}


::-webkit-scrollbar-thumb {
 background: linear-gradient(135deg, #8b5cf6, #a78bfa);
 border-radius: 10px;
 border: 2px solid #000000;
}


::-webkit-scrollbar-thumb:hover {
 background: linear-gradient(135deg, #a78bfa, #c4b5fd);
}
</style>
""", unsafe_allow_html=True)
# -----------------------------
# Header (locked UI)
# -----------------------------
col1, col2 = st.columns([1, 12])
with col1:
    try:
        st.image("logo.jpg", width=80)
    except Exception:
        st.markdown('<span style="font-size: 3.5rem; filter: drop-shadow(0 0 20px rgba(0, 217, 255, 0.6));">🔷</span>', unsafe_allow_html=True)
with col2:
    st.markdown(
        """
        <div class="main-header" style="margin-top: -10px;">
            <span style="font-size: 3rem; font-weight: 900; background: linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">PRISMA</span>
            <p class='glow-text' style='font-size: 1.3rem; color: #a78bfa; margin-top: 0.5rem;'>AI-Powered Insight Generator — Analyze, Understand, and Chat with Your Data</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# File Upload Section
# -----------------------------
st.markdown("""
<h3 style='
    font-size: 1.8rem; 
    margin-bottom: 1.2rem; 
    background: linear-gradient(135deg, #ffffff 0%, #a78bfa 60%, #8b5cf6 100%);
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    letter-spacing: -0.02em;
'>
📂 Upload your CSV dataset
</h3>
""", unsafe_allow_html=True)


uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"], help="Upload a CSV file to analyze")

# -----------------------------
# Data Handling Section
# -----------------------------
if uploaded_file is not None:
    with st.spinner(" Loading dataset..."):
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except Exception:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='latin-1')
        time.sleep(0.8)

    st.success(f"✅ Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns")
    st.markdown("### 🧾 Dataset Preview")
    st.dataframe(df.head(10), use_container_width=True)

    # --- Browse Data: Paging & Download ---
    st.markdown("---")
    browse = st.expander(" Browse & Download Full Data", expanded=False)
    with browse:
        page_size = st.number_input(
            "Rows per page (for Browse Data)", min_value=10, max_value=1000, value=25, step=5
        )
        total_rows = df.shape[0]
        page_count = (total_rows - 1) // page_size + 1
        page = st.number_input(
            f"Page [1-{page_count}]", min_value=1, max_value=max(1, page_count), value=1, step=1
        )
        start = (page - 1) * page_size
        end = min(start + page_size, total_rows)
        st.dataframe(df.iloc[start:end], use_container_width=True)
        st.download_button(
            "⬇️ Download Full Data as CSV", data=df.to_csv(index=False), file_name="prisma_data.csv"
        )

    # --- Target Selection ---
    st.markdown("### 🎯 Select Target Column (Optional)")
    target_col = st.selectbox(
        "Select a target column for prediction or analysis (optional):",
        ["None"] + list(df.columns))

    # --- AI Insight Generation ---
    st.markdown("<div class='insights-card'>", unsafe_allow_html=True)
    st.markdown("### 💡 AI-GENERATED INSIGHTS")

    summary = df.describe(include='all').to_string()
    prompt = f"""
    You are Prisma, an AI data analyst.
    Analyze the following dataset summary and generate 5 meaningful, human-friendly insights
    that could help a business or educator make decisions.

    Dataset Summary:
    {summary}
    """
    with st.spinner("✨ Generating insights using Ollama..."):
        insights = query_ollama(prompt)
    st.markdown(f"<div class='insights-content'>{insights}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Chat With Your Data ---
    st.markdown("<div class='insights-card'>", unsafe_allow_html=True)
    st.markdown("### 💬 CHAT WITH YOUR DATA")
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(167, 139, 250, 0.08) 100%);
                padding: 1.8rem; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.3); margin-bottom: 2rem;'>
        <p style='color:#c4b5fd; font-weight: 700; font-size: 1.15rem; margin-bottom: 0.8rem;'>💡 Ask intelligent questions:</p>
        <p style='color:#e2e8f0; line-height: 2; margin: 0; font-size: 1.05rem;'>
        • "Why did profits drop in 2020?"<br>
        • "Which subject has the highest marks?"<br>
        • "What affects sales the most?"
        </p>
    </div>
    """, unsafe_allow_html=True)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_question = st.text_input("", placeholder="✨ Ask Prisma anything about your dataset...")

    if st.button("ASK PRISMA"):
        if user_question.strip():
            with st.spinner("🤖 Analyzing your question..."):
                summary = df.describe(include='all').to_string()
                prompt = f"""
                You are Prisma, an AI Data Analyst.
                Use the dataset summary below to answer the question in a clear, concise, human-friendly way.

                Dataset Summary:
                {summary}

                Question: {user_question}
                """
                response = query_ollama(prompt)
            st.session_state.chat_history.append({"q": user_question, "a": response})
        else:
            st.warning("⚠️ Please enter a question to ask Prisma.")

    # --- Display Chat History ---
    if st.session_state.chat_history:
        st.markdown("<div style='margin-top: 2.5rem;'>", unsafe_allow_html=True)
        for idx, chat in enumerate(st.session_state.chat_history[::-1]):
            st.markdown(f"""
            <div class='chat-message' style='animation-delay: {idx * 0.1}s;'>
                <p style='color: #c4b5fd; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.8rem;'>🧑 You:</p>
                <p style='color: #e2e8f0; margin-bottom: 1.2rem; padding-left: 1.5rem; font-size: 1.05rem;'>{chat['q']}</p>
                <p style='color: #a78bfa; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.8rem;'>🤖 Prisma:</p>
                <div style='color: #e2e8f0; padding-left: 1.5rem; line-height: 1.9; font-size: 1.05rem;'>{chat['a']}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown("""
    <div style='text-align: center; padding: 4rem; animation: pulse 3s ease-in-out infinite;'>
        <h3 style='font-size: 1.8rem; margin-bottom: 1.2rem; background: linear-gradient(135deg, #ffffff 0%, #a78bfa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        ⬆️ Upload a CSV file to unlock AI-powered insights
        </h3>
        <p style='color: #a78bfa; font-size: 1.2rem; font-weight: 500;'>Transform your data into actionable intelligence</p>
    </div>
    """, unsafe_allow_html=True)
