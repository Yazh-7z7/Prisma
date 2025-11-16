# 🧠 Prisma: Smart Insight Generator

### Overview
**Prisma** is an AI-powered system that analyzes student or business data and automatically generates meaningful discussion questions and insights — helping teachers, managers, and analysts focus on what matters most.

---

### 🚀 Tech Stack
- **Python 3.13**
- **Streamlit** — Front-end for interactive data upload and visualization  
- **Ollama (Gemma3:4b)** — Local LLM for generating insights  
- **MySQL** — For structured data storage and retrieval  
- **Pandas & Scikit-learn** — For data cleaning and preprocessing  

---

### ⚙️ Project Structure
prisma/
│
├── data/ # Raw CSV files
├── outputs/ # Cleaned datasets
├── scripts/
│ ├── preprocess.py # Cleans and prepares data
│ └── insight_generator.py # Uses Ollama to generate insights
│
├── app.py # Streamlit main app (UI)
├── requirements.txt # Dependencies
└── README.md 

---

### 🧩 Setup Instructions
```bash
git clone https://github.com/YOURUSERNAME/Prisma.git
cd Prisma
pip install -r requirements.txt
streamlit run app.py

Example Use Case

Upload student marks or sales data →
Prisma cleans it →
Ollama generates natural language insights like:
Why did the average marks drop this month?
Which regions show the strongest sales trend? 

