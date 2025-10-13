import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, r2_score
import joblib

# === Step 1: Get file path ===
data_path = input("Enter the path to your CSV file (e.g., data/yourfile.csv): ").strip()

if not os.path.exists(data_path):
    raise FileNotFoundError(f"❌ File not found: {data_path}")

df = pd.read_csv(data_path)
print(f"\n✅ Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns")
print("📊 Columns:", list(df.columns))

# === Step 2: Choose target column ===
target_column = input("\nEnter the target column name (the column you want to predict): ").strip()

if target_column not in df.columns:
    raise ValueError(f"❌ Column '{target_column}' not found in dataset.")

X = df.drop(columns=[target_column])
y = df[target_column]

# === Step 3: Preprocess ===
# Convert categorical features
for col in X.columns:
    if X[col].dtype == 'object':
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))

# Handle missing values
X.fillna(X.mean(numeric_only=True), inplace=True)
if y.isnull().any():
    y.fillna(y.mean() if y.dtype != 'object' else y.mode()[0], inplace=True)

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# === Step 4: Detect task type ===
if np.issubdtype(y.dtype, np.number):
    task_type = "regression"
else:
    # Non-numeric (text/categorical) targets => classification
    task_type = "classification"

print(f"\n🧩 Detected task type: {task_type.upper()}")

# Encode target if classification
if task_type == "classification" and y.dtype == 'object':
    y = LabelEncoder().fit_transform(y)

# === Step 5: Split and train ===
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

if task_type == "regression":
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    score = r2_score(y_test, preds)
    print(f"✅ Regression model trained successfully! R² Score: {score:.3f}")
else:
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    score = accuracy_score(y_test, preds)
    print(f"✅ Classification model trained successfully! Accuracy: {score:.3f}")

# === Step 6: Save model ===
os.makedirs("models", exist_ok=True)
model_name = os.path.basename(data_path).replace(".csv", "_model.pkl")
model_path = os.path.join("models", model_name)
joblib.dump(model, model_path)

print(f"💾 Model saved as: {model_path}")

