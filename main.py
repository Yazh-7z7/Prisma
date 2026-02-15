import argparse
import sys
import os
import pandas as pd

# Add src to python path to allow imports if running from root
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils import setup_logging, load_config, load_dataset
from statistical_engine import StatisticalEngine
from llm_generator import LLMGenerator
from insight_parser import InsightParser
from validator import Validator
from hallucination_detector import HallucinationDetector
from report_generator import ReportGenerator

def main():
    parser = argparse.ArgumentParser(description="Prisma Hallucination Insight Generator")
    parser.add_argument("--dataset", help="Path to dataset CSV (overrides config)")
    parser.add_argument("--model", default="claude-3-sonnet-20240229", help="LLM model to use")
    parser.add_argument("--provider", default="anthropic", help="LLM provider (anthropic/openai/ollama)")
    args = parser.parse_args()
    
    logger = setup_logging()
    config = load_config("config/config.yaml")
    
    # 1. Load Data
    dataset_path = args.dataset if args.dataset else os.path.join(config['data']['raw_dir'], config['data']['datasets'][0]['filename'])
    logger.info(f"Loading dataset from {dataset_path}...")
    
    if not os.path.exists(dataset_path):
        logger.error(f"Dataset not found: {dataset_path}")
        # Create a dummy dataset for testing if none exists
        logger.info("Creating dummy dataset for demonstration...")
        data = {
            'age': [25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
            'cholesterol': [180, 190, 200, 210, 220, 230, 240, 250, 260, 270], # Perfect correlation
            'income': [50000, 52000, 51000, 53000, 52000, 54000, 53000, 55000, 54000, 56000], # Weak correlation
            'random': [1, 9, 2, 8, 3, 7, 4, 6, 5, 0] # Random
        }
        df = pd.DataFrame(data)
        os.makedirs(os.path.dirname(dataset_path), exist_ok=True)
        df.to_csv(dataset_path, index=False)
    else:
        df = load_dataset(dataset_path)
    
    if df is None:
        return

    # 2. Statistical Analysis (Ground Truth)
    stats_engine = StatisticalEngine(config)
    ground_truth = stats_engine.analyze_dataset(df)
    
    # 3. LLM Generation
    llm_gen = LLMGenerator(config)
    # Create a simple summary for the LLM
    dataset_summary = df.describe().to_string()
    
    logger.info(f"Requesting insights from {args.model}...")
    llm_output = llm_gen.generate_insights(
        dataset_summary, 
        model_provider=args.provider, 
        model_name=args.model
    )
    
    if not llm_output:
        logger.error("Failed to get LLM output.")
        return

    logger.info("LLM Output received.")
    print("\n--- LLM Response ---\n")
    print(llm_output[:500] + "..." if len(llm_output) > 500 else llm_output)
    print("\n--------------------\n")

    # 4. Parse Insights
    parser = InsightParser()
    parsed_claims = parser.parse_insights(llm_output)
    
    # 5. Validate
    validator = Validator(config)
    validation_results = validator.validate_claims(parsed_claims, ground_truth, df.columns)
    
    # 6. Detect Hallucinations
    detector = HallucinationDetector(config)
    metrics = detector.calculate_metrics(validation_results)
    
    logger.info(f"Analysis Complete. Hallucination Rate: {metrics['hallucination_rate']}")
    
    # 7. Generate Report
    reporter = ReportGenerator(config)
    report_path = reporter.generate_reports(
        validation_results, 
        metrics, 
        dataset_name=os.path.basename(dataset_path),
        model_name=args.model
    )
    
    print(f"\nReport generated at: {report_path}")

if __name__ == "__main__":
    main()
