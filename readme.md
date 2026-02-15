# 🧠 Prisma: Smart Insight Generator & Hallucination Detector

### Overview
**Prisma** is a dual-purpose AI system:
1.  **Insight Generation**: Analyzes student or business data to generate meaningful discussion questions and insights using LLMs.
2.  **Hallucination Detection**: A research-grade module that statistically validates AI-generated insights against ground truth data to measure and prevent hallucinations.

---

### 🚀 Tech Stack
-   **Python 3.13**
-   **Streamlit** — Front-end for interactive data upload and visualization
-   **Ollama (Gemma3:4b)** — Local LLM for generating insights
-   **Claude & GPT-4** — API-based models for high-fidelity benchmarks
-   **MySQL** — For structured data storage and retrieval
-   **Pandas & Scikit-learn** — For data cleaning and preprocessing
-   **Statsmodels & Scipy** — For statistical ground truth validation

---

### ⚙️ Project Structure
```text
Prisma/
├── data/
│   ├── raw/              # Original datasets
│   └── ground_truth/     # Statistical analysis results
├── src/
│   ├── statistical_engine.py  # Calculates real correlations/stats
│   ├── llm_generator.py       # Fetches insights from LLMs
│   ├── insight_parser.py      # Extracts claims from LLM text
│   ├── validator.py           # Checks claims against ground truth
│   ├── hallucination_detector.py # Computes hallucination rates
│   ├── report_generator.py    # Generates validation reports
│   └── utils.py
├── config/
│   ├── config.yaml       # System configuration
│   └── prompts.yaml      # Prompt templates
├── experiments/          # Scripts for running benchmarks
├── results/              # Output reports and metrics
├── app.py                # Streamlit main app (UI)
├── requirements.txt      # Dependencies
└── README.md
```

### 🧩 Hallucination Detection Workflow
1.  **Input**: Structured dataset (CSV).
2.  **Ground Truth**: Statistical Engine runs exhaustive tests (correlations, ANOVA, etc.).
3.  **Generation**: LLM analyzes data summary and generates unexpected patterns.
4.  **Validation**: System parses specific claims ("Age correlates with X") and checks them against statistical ground truth.
5.  **Reporting**: Outputs Hallucination Rate (HR), validated insights, and detailed metrics.

---

### 🧩 Setup Instructions
```bash
git clone https://github.com/YOURUSERNAME/Prisma.git
cd Prisma
pip install -r requirements.txt
python main.py  # Run the Hallucination Detector pipeline
# OR
streamlit run app.py # Run the Interactive UI
```

