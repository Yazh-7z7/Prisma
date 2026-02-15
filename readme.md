# Prisma: Hallucination-Aware Insight Generator

**Prisma** is an advanced AI system designed to generate meaningful data insights while rigorously detecting and preventing hallucinations. It combines the creative power of Large Language Models (LLMs) with the precision of statistical analysis to ensure every claim is backed by data.

---

## Key Features

### 1. Multi-Model Insight Generation
-   **Universal Support**: Works with **Ollama (Local)**, **Anthropic (Claude 3)**, and **OpenAI (GPT-4)**.
-   **Context-Aware**: Feeds statistical summaries to LLMs to ground generation in reality.
-   **Prompt Strategies**: Uses specialized prompts to encourage analytical depth over generic observations.

### 2. Statistical Guardrails (The "Truth Engine")
Prisma doesn't just trust the LLM. It verifies every claim using a robust statistical engine:
-   **Correlation Analysis**: Pearson & Spearman correlations with p-value significance testing.
-   **Group Differences**: T-tests and ANOVA to validate claims about group variances (e.g., *"Men have higher heart disease rates"*).
-   **Categorical Associations**: Chi-Square tests for relationships between categorical variables.
-   **Distribution Checks**: Verifies claims about means, medians, and outliers using Z-scores and IQR.

### 3. Hallucination Detection
Every generated insight undergoes a 3-step validation process:
1.  **Parsing**: Extracts variables, relationships, and claimed strength/direction from natural language.
2.  **Verification**: queries the pre-computed "Ground Truth" for evidence.
3.  **Classification**: Flags insights as:
    -    **VALID**: Statistically supported.
    -    **UNVERIFIED**: specific variables not found or relationship too complex.
    -    **HALLUCINATION**: Contradicted by data (e.g., claiming positive correlation when it's negative or insignificant).

### 4. Interactive Dashboard (Streamlit)
A modern, glassmorphic UI for real-time analysis:
-   **Drag & Drop Data**: Upload CSV/Excel files instantly.
-   **Live Validation**: See insights validated in real-time with color-coded badges.
-   **Visual Evidence**: Click any insight to see the underlying scatter plots, box plots, or contingency tables.
-   **Report Generation**: Download comprehensive Markdown/JSON reports.

---

## System Architecture

The system is built on a modular pipeline architecture:

```mermaid
graph TD
    A[Input Data (CSV)] --> B(Statistical Engine)
    A --> C(LLM Generator)
    B --> D{Ground Truth Store}
    D --> C
    C --> E[Raw Insights]
    E --> F(Insight Parser)
    F --> G[Structured Claims]
    G --> H(Validator)
    D --> H
    H --> I[Validated Insights]
    I --> J(Report Generator)
    I --> K(Streamlit Dashboard)
```

### Core Modules (`src/`)
-   **`statistical_engine.py`**: The mathematical backbone. Computes all valid relationships in the dataset beforehand.
-   **`llm_generator.py`**: Handles API communication (Ollama/Anthropic/OpenAI) with error handling and retries.
-   **`insight_parser.py`**: Uses NLP heuristics (and potentially fuzzy matching) to convert text into structured data objects.
-   **`validator.py`**: The judge. Compares structured claims against the Ground Truth store.
-   **`hallucination_detector.py`**: Aggregates metrics (Hallucination Rate, Precision, Recall).

---

## Installation & Setup

### Prerequisites
-   Python 3.10+
-   [Ollama](https://ollama.com/) (optional, for local models)

### 1. Clone & Install
```bash
git clone https://github.com/Yazh-7z7/Prisma.git
cd Prisma
pip install -r requirements.txt
```

### 2. Configure API Keys
Prisma uses a local `.env` file for security. Create one in the root directory:
```bash
touch .env
```
Add your keys (leave empty if using Ollama):
```env
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### 3. Run the Application
**Interactive UI (Recommended):**
```bash
streamlit run app.py
```
**Command Line Pipeline:**
```bash
python main.py --dataset data/raw/healthcare_dataset_stroke_data.csv --provider ollama
```

---

## Validation Logic Details

### How we define "Hallucination"
In the context of Data Analysis, a hallucination is defined as:
> *A claim about a relationship or statistic that is either **statistically insignificant** (p > 0.05) or **contradicted** by the calculated ground truth (e.g., wrong direction).*

### Supported Validation Types
| Claim Type | Statistical Test | Example |
| :--- | :--- | :--- |
| **Correlation** | Pearson/Spearman (p<0.05) | *"Age is strongly correlated with BMI"* |
| **Group Difference** | T-test / ANOVA | *"Smokers have higher stroke risk"* |
| **Association** | Chi-Square | *"Gender is associated with work type"* |
| **Descriptive** | Mean/Median/Count | *"Average glucose level is 106.14"* |

---

## Project Structure

```text
Prisma/
├── app.py                 # Streamlit Dashboard Entry Point
├── main.py                # CLI Entry Point
├── config/
│   ├── config.yaml        # Thresholds & settings
│   └── prompts.yaml       # LLM System Prompts
├── data/                  # Data storage
├── src/                   # Source Code
│   ├── statistical_engine.py
│   ├── validator.py
│   ├── llm_generator.py
│   └── ...
├── results/               # Generated Reports
└── requirements.txt       # Dependencies
```

---

## Contributing
Contributions are welcome! Please read the [implementation plan](implementation_plan.md) to understand the roadmap.

