# -----------------------------------------------------------
# 🔮 PRISMA – ENHANCED FRONTEND (No Backend Code Changed)
# -----------------------------------------------------------

import streamlit as st
import pandas as pd
import subprocess
import time

# -----------------------------------
# Backend function (UNTOUCHED)
# -----------------------------------
def query_ollama(prompt: str, model: str = "gemma3:4b"):
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

# -----------------------------------
# Enhanced Page Config
# -----------------------------------
st.set_page_config(
    page_title="Prisma – AI-Powered Insight Generator",
    page_icon="🔷",
    layout="wide"
)

# -----------------------------------
# Modern UI CSS 2.0 (Frontend ONLY)
# -----------------------------------
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');

html, body {
    font-family: 'Inter', sans-serif !important;
}

/* Global background */
.stApp {
    background: radial-gradient(circle at 20% 20%, #1a1a2e, #000000 70%);
}

/* Section cards */
.section-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    padding: 2rem 2.5rem;
    border-radius: 20px;
    margin-top: 25px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.45);
    backdrop-filter: blur(14px);
    animation: fadeIn 0.7s ease-out;
}

/* Fade animation */
@keyframes fadeIn {
    from {opacity: 0; transform: translateY(20px);}
    to   {opacity: 1; transform: translateY(0);}
}

/* Main title styling */
.prisma-title {
    font-size: 3.8rem;
    font-weight: 900;
    letter-spacing: -2px;
    background: linear-gradient(90deg, #ffffff, #c4b5fd, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: -10px;
}

/* Subtitle */
.prisma-sub {
    font-size: 1.25rem;
    color: #b9a8fc;
    margin-bottom: 2.5rem;
}

/* File uploader */
.stFileUploader {
    background: rgba(255, 255, 255, 0.04) !important;
    border-radius: 16px !important;
    padding: 2.2rem !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

.stFileUploader:hover {
    transform: translateY(-4px);
    transition: 0.3s;
    box-shadow: 0 10px 28px rgba(139,92,246,0.25);
}

/* Button */
.stButton>button {
    background: linear-gradient(135deg, #8b5cf6, #a78bfa);
    padding: 0.8rem 2rem;
    border-radius: 12px;
    border: none;
    color: white;
    font-weight: 700;
    transition: all .25s;
}

.stButton>button:hover {
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 10px 28px rgba(139,92,246,0.35);
}

/* Insights card */
.insight-box {
    background: rgba(255,255,255,0.04);
    border-left: 5px solid #a78bfa;
    padding: 1.5rem;
    border-radius: 16px;
    margin-top: 1.5rem;
    animation: fadeIn 1s ease-out;
}

/* Chat bubbles */
.chat-message {
    background: rgba(255,255,255,0.05);
    padding: 1.3rem;
    border-radius: 18px;
    margin-bottom: 1rem;
    border-left: 4px solid #8b5cf6;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------
# HEADER (unchanged logic, new styling)
# -----------------------------------
st.markdown("""
<div class="header-area" style="text-align: left;">
    <h1 class="prisma-title">PRISMA</h1>
    <p class="prisma-sub">AI-Powered Insight Generator — Analyze, Understand & Chat With Your Data</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------
# FILE UPLOAD SECTION (same backend)
# -----------------------------------
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("### 📁 Upload Your Dataset")
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------
# DATA HANDLING & DISPLAY (exact backend, new UI)
# -----------------------------------
if uploaded_file:
    
    df = pd.read_csv(uploaded_file)

    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.success(f"Dataset Loaded: {df.shape[0]} rows × {df.shape[1]} columns")
    st.dataframe(df.head(), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Target column selection (unchanged)
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 🎯 Select Target Column")
    target_col = st.selectbox("Choose target column:", ["None"] + list(df.columns))
    st.markdown("</div>", unsafe_allow_html=True)

    # Insights (unchanged backend)
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 💡 AI-Generated Insights")
    summary = df.describe(include='all').to_string()
    insights = query_ollama(
        f"Generate 5 insights based on this data:\n{summary}"
    )
    st.markdown(f"<div class='insight-box'>{insights}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Chat section (unchanged backend)
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 💬 Chat with Your Data")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input("Ask a question about this dataset")

    if st.button("Ask Prisma"):
        if user_q.strip():
            summary = df.describe(include='all').to_string()
            ans = query_ollama(f"Dataset:\n{summary}\nQ: {user_q}\nA:")
            st.session_state.chat_history.append({"q": user_q, "a": ans})

    for msg in st.session_state.chat_history[::-1]:
        st.markdown(f"""
        <div class='chat-message'>
            <b>You:</b> {msg['q']}<br><br>
            <b>Prisma:</b> {msg['a']}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown("""
    <div style="text-align:center; margin-top:3rem;">
        <h2 style="color:#c4b5fd;">Upload a CSV file to get started ✨</h2>
    </div>
    """, unsafe_allow_html=True)
