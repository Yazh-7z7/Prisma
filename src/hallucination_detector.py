class HallucinationDetector:
    def __init__(self, config):
        self.config = config

    def calculate_metrics(self, validation_results):
        """
        Computes hallucination rates and other metrics.
        """
        total_claims = len(validation_results)
        if total_claims == 0:
            return {
                "total_claims": 0,
                "valid_claims": 0,
                "hallucinations": 0,
                "unverified": 0,
                "hallucination_rate": 0.0,
                "insight_validity_score": 0.0
            }
            
        valid_count = sum(1 for r in validation_results if r['status'] == 'VALID')
        hallucination_count = sum(1 for r in validation_results if 'HALLUCINATION' in r['status'])
        unverified_count = sum(1 for r in validation_results if r['status'] == 'UNVERIFIED')
        
        # Hallucination Rate
        hr = hallucination_count / total_claims
        
        # Insight Validity Score
        ivs = valid_count / total_claims
        
        metrics = {
            "total_claims": total_claims,
            "valid_claims": valid_count,
            "hallucinations": hallucination_count,
            "unverified": unverified_count,
            "hallucination_rate": round(hr, 4),
            "insight_validity_score": round(ivs, 4)
        }
        
        return metrics
