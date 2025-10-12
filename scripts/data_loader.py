import pandas as pd
import os

def load_data(file_path: str):
    """
    Loads a dataset based on file extension.
    Supports CSV, Excel, and JSON.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found")

    ext = os.path.splitext(file_path)[-1].lower()

    if ext == '.csv':
        return pd.read_csv(file_path)
    elif ext in ['.xls', '.xlsx']:
        return pd.read_excel(file_path)
    elif ext == '.json':
        return pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

if __name__ == "__main__":
    data_dir = "data"
    for file in os.listdir(data_dir):
        df = load_data(os.path.join(data_dir, file))
        print(f"✅ Loaded {file} with shape {df.shape}")
