import logging
import yaml
import pandas as pd
import os
from datetime import datetime

def setup_logging(name="Prisma"):
    """
    Sets up logging configuration.
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{name}_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(name)

def load_config(config_path="config/config.yaml"):
    """
    Loads configuration from a YAML file.
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def load_prompts(prompts_path="config/prompts.yaml"):
    """
    Loads prompts from a YAML file.
    """
    try:
        with open(prompts_path, 'r') as file:
            prompts = yaml.safe_load(file)
        return prompts
    except Exception as e:
        print(f"Error loading prompts: {e}")
        return {}

def load_dataset(file_path):
    """
    Loads a dataset from a CSV file.
    """
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        print(f"Error loading dataset {file_path}: {e}")
        return None

def save_json(data, file_path):
    """
    Saves data to a JSON file.
    """
    import json
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
            
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Successfully saved to {file_path}")
    except Exception as e:
        print(f"Error saving JSON to {file_path}: {e}")
