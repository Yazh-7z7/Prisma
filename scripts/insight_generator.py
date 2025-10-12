import os
import pandas as pd
import subprocess

def query_ollama(prompt: str, model: str = "gemma3:4b"):
    """
    Queries Ollama locally via subprocess and returns the model output.
    Handles encoding issues for Windows (UTF-8 safe).
    """
    command = ["ollama", "run", model]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"   # replaces problematic characters instead of crashing
    )

    output, error = process.communicate(input=prompt)

    if error and error.strip():
        print("⚠️ Ollama error:", error)
    return output.strip()

def generate_insights(file_path: str):
    """
    Generates 5 discussion insights/questions for the given dataset
    using Ollama's local LLM.
    """
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='latin-1')

    summary = df.describe(include='all').to_string()

    prompt = f"""
    You are a data analyst AI. Analyze this dataset summary and generate 5 meaningful discussion questions 
    or insights that a teacher or business manager might want to discuss.
    Dataset summary:
    {summary}
    """

    print("🧠 Generating insights using Ollama...")
    response = query_ollama(prompt)
    return response

if __name__ == "__main__":
    data_dir = "outputs"
    if not os.path.exists(data_dir):
        print("⚠️ No 'outputs' folder found. Please run preprocessing first.")
    else:
        for file in os.listdir(data_dir):
            if file.endswith("_cleaned.csv"):
                path = os.path.join(data_dir, file)
                print(f"\n📊 Insights for {file}:")
                insights = generate_insights(path)
                print(insights)
