import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
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
label_encoders = {}
for col in X.columns:
    if X[col].dtype == 'object':
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le

# Handle missing values
X.fillna(X.mean(numeric_only=True), inplace=True)
if y.isnull().any():
    if y.dtype == 'object':
        y.fillna(y.mode().iloc[0], inplace=True)
    else:
        y.fillna(y.mean(), inplace=True)

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# === Step 4: Detect task type ===
try:
    is_numeric = np.issubdtype(y.dtype, np.number)
except TypeError:
    # fallback if y.dtype is object-like
    is_numeric = False

if is_numeric:
    task_type = "regression"
else:
    task_type = "classification"

print(f"\n🧩 Detected task type: {task_type.upper()}")

# Encode target if classification and it's object
target_le = None
if task_type == "classification" and y.dtype == 'object':
    target_le = LabelEncoder()
    y = target_le.fit_transform(y.astype(str))

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
base_name = os.path.splitext(os.path.basename(data_path))[0]
model_name = f"{base_name}_model.pkl"
model_path = os.path.join("models", model_name)
joblib.dump(model, model_path)

# Optionally save scaler and encoders for inference
joblib.dump(scaler, os.path.join("models", f"{base_name}_scaler.pkl"))
if label_encoders:
    joblib.dump(label_encoders, os.path.join("models", f"{base_name}_label_encoders.pkl"))
if target_le is not None:
    joblib.dump(target_le, os.path.join("models", f"{base_name}_target_encoder.pkl"))

print(f"💾 Model and artifacts saved in: models/")
