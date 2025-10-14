import streamlit as st
import pandas as pd

st.title("🔍 File Upload Test")

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    df = pd.read_csv(uploaded_file)
    st.dataframe(df.head())
else:
    st.info("Please upload a CSV file.")
