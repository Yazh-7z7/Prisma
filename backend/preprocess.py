import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler, MinMaxScaler

def clean_dataframe(df: pd.DataFrame):
    """
    Cleans and standardizes a dataframe intelligently.
    - Detects missing values and fills them (median/mode)
    - Removes duplicate rows
    - Standardizes numeric columns
    - Normalizes categorical strings
    """
    df = df.copy()

    # Drop duplicates
    df.drop_duplicates(inplace=True)

    # Handle missing values
    for col in df.columns:
        if df[col].dtype in [np.float64, np.int64]:
            df[col].fillna(df[col].median(), inplace=True)
        else:
            df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "Unknown", inplace=True)

    # Normalize string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip().str.lower()

    return df


def scale_numerical_data(df: pd.DataFrame, mode="standard"):
    """
    Scales numeric features using StandardScaler or MinMaxScaler.
    """
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) == 0:
        return df

    scaler = StandardScaler() if mode == "standard" else MinMaxScaler()
    df[num_cols] = scaler.fit_transform(df[num_cols])
    return df


def summarize_dataset(df: pd.DataFrame, name="Dataset"):
    """
    Prints key statistics and structure.
    """
    print(f"\n {name} Summary:")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Missing values:\n{df.isnull().sum()}")
    print(f"Sample data:\n{df.head(3)}")


if __name__ == "__main__":
    data_dir = "data"
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(data_dir):
        path = os.path.join(data_dir, file)
        name = file.split(".")[0]

        try:
            df = pd.read_csv(path)
        except:
            continue

        summarize_dataset(df, name)

        cleaned_df = clean_dataframe(df)
        scaled_df = scale_numerical_data(cleaned_df)

        output_path = os.path.join(output_dir, f"{name}_cleaned.csv")
        scaled_df.to_csv(output_path, index=False)

        print(f" Cleaned & saved: {output_path}")
df.to_csv("processed_data.csv", index=False)
print(" Preprocessed data saved to data/processed_data.csv")
