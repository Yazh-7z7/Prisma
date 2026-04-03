import os
import json
import logging
from datetime import datetime

class ReportGenerator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.ReportGenerator")
        # Use output section from config
        self.results_dir = config.get('output', {}).get('results_dir', 'results')
        self.reports_dir = config.get('output', {}).get('reports_dir', 'results/reports')
        self.metrics_dir = config.get('output', {}).get('metrics_dir', 'results/metrics')

    def generate_reports(self, validation_results, metrics, dataset_name, model_name):
        """
        Generates reports in JSON and Markdown formats.
        """
        self.logger.info("Generating reports...")
        
        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_readable = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # User requested scheme: "name-of-dataset_time"
        # Removing model name from filename as implied by request
        base_filename = f"{dataset_name}_{timestamp_file}"
        
        # Ensure output directories exist
        os.makedirs(self.metrics_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        
        json_path = os.path.join(self.metrics_dir, f"{base_filename}.json")
        md_path = os.path.join(self.reports_dir, f"{base_filename}.md")
        
        # Prepare full results object
        full_results = {
            "metadata": {
                "dataset": dataset_name,
                "model": model_name,
                "timestamp": timestamp_readable
            },
            "metrics": metrics,
            "validation_details": validation_results
        }
        
        # Save JSON
        with open(json_path, 'w') as f:
            json.dump(full_results, f, indent=4)
        self.logger.info(f"JSON report saved to {json_path}")
        
        # Save Markdown
        self._save_markdown_report(full_results, md_path)
        self.logger.info(f"Markdown report saved to {md_path}")
        
        return md_path

    def _save_markdown_report(self, results, filepath):
        """
        Generates a human-readable markdown report.
        """
        metrics = results['metrics']
        details = results['validation_details']
        
        md_content = f"""# Hallucination Analysis Report
**Dataset:** {results['metadata']['dataset']}
**Model:** {results['metadata']['model']}
**Date:** {results['metadata']['timestamp']}

## Executive Summary
- **Total Claims:** {metrics['total_claims']}
- **Valid Claims:** {metrics['valid_claims']}
- **Hallucinations:** {metrics['hallucinations']}
- **Hallucination Rate:** {metrics['hallucination_rate'] * 100:.2f}%
- **Insight Validity Score:** {metrics['insight_validity_score'] * 100:.2f}%

## Detailed Validation
"""
        
        for idx, item in enumerate(details):
            status_icon = "✅" if item['status'] == "VALID" else "❌" if "HALLUCINATION" in item['status'] else "⚠️"
            
            md_content += f"""
### {idx+1}. {status_icon} {item['status']}
**Claim:** "{item['claim']['original_text']}"
**Reason:** {item['reason']}
"""
            if item.get('ground_truth'):
                gt = item['ground_truth']
                md_content += f"**Ground Truth:** {gt['var1']} vs {gt['var2']} ({gt.get('strength', 'unknown')} {gt.get('direction', 'unknown')})\n"
                
        with open(filepath, 'w') as f:
            f.write(md_content)
