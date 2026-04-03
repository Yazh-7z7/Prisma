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
        errors="replace"
    )

    output, error = process.communicate(input=prompt)

    if error and error.strip():
        print(" Ollama error:", error)
    return output.strip()

def generate_insights(file_path: str):
    """
    Generates structured, readable insights using Ollama.
    """
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='latin-1')

    summary = df.describe(include='all').to_string()

    prompt = f"""
    You are an AI Data Analyst named Prisma. Analyze the dataset below and generate
    7 highly readable insights in structured markdown format.

    Each insight should include:
    1. A clear **title**
    2. A short **interpretation**
    3. A **reason or possible cause**
    4. A **potential action or next step**

    Dataset summary:
    {summary}

    Format response in bullet points or numbered list. Avoid technical jargon.
    """

    print("🧠 Generating enhanced insights using Ollama...")
    response = query_ollama(prompt)
    return response

if __name__ == "__main__":
    data_dir = "outputs"
    if not os.path.exists(data_dir):
        print(" No 'outputs' folder found. Please run preprocessing first.")
    else:
        for file in os.listdir(data_dir):
            if file.endswith("_cleaned.csv"):
                path = os.path.join(data_dir, file)
                print(f" Generating insights for {file}...")
                insights = generate_insights(path)
                print(f"\n{insights}\n")

