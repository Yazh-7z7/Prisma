import logging
from fuzzywuzzy import process, fuzz
import re

class Validator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.Validator")
        self.match_threshold = config['validation']['match_threshold'] * 100

    def validate_claims(self, claims, ground_truth, df_columns):
        """
        Validates a list of claims against ground truth.
        """
        self.logger.info("Validating claims...")
        validated_claims = []
        
        for claim in claims:
            validation_result = self._validate_single_claim(claim, ground_truth, df_columns)
            validated_claims.append(validation_result)
            
        return validated_claims

    def _validate_single_claim(self, claim, ground_truth, df_columns):
        """
        Validates a single claim.
        """
        # 1. Extract variables from claim text if not already structured
        text = claim['original_text']
        
        # Try to find variables mentioned in the text
        mentioned_vars = self._extract_variables(text, df_columns)
        
        claim_result = {
            "claim": claim,
            "extracted_vars": mentioned_vars,
            "status": "UNVERIFIED",
            "reason": "Not enough variables found"
        }
        
        # --- NEW: Metadata Validation (Sample size, etc.) ---
        if "sample size" in text.lower() or "n=" in text.lower():
            return self._validate_metadata(text, ground_truth, claim_result)

        # --- NEW: Single Variable Validation (Mean, Range, etc.) ---
        if len(mentioned_vars) == 1:
            return self._validate_descriptive_stats(text, mentioned_vars[0], ground_truth, claim_result)

        if len(mentioned_vars) < 2:
            return claim_result
            
        # We assume the first two found vars are the subject of the relationship
        var1, var2 = mentioned_vars[0], mentioned_vars[1]
        
        # 2. Check if relationship exists in ground truth
        truth = self._find_truth(var1, var2, ground_truth)
        
        if not truth:
            claim_result["status"] = "HALLUCINATION_RELATIONSHIP"
            claim_result["reason"] = f"No statistical relationship found between {var1} and {var2}"
            return claim_result
            
        # 3. Check direction and strength
        # Simple check: does direction match?
        claimed_direction = claim.get('direction', 'unknown')
        true_direction = truth['direction']
        
        if claimed_direction != "unknown" and claimed_direction != true_direction:
            claim_result["status"] = "HALLUCINATION_DIRECTION"
            claim_result["reason"] = f"Claimed {claimed_direction}, but actually {true_direction}"
            claim_result['ground_truth'] = truth
            return claim_result

        # If we pass these checks, it's valid (or at least plausible)
        claim_result["status"] = "VALID"
        claim_result["reason"] = "Relationship confirmed by statistics"
        claim_result['ground_truth'] = truth
        
        return claim_result

    def _extract_variables(self, text, columns):
        """
        Uses fuzzy matching to identify columns in text.
        """
        found = []
        # Pre-process text to remove common words? Maybe not needed for simple matching.
        
        for col in columns:
            # Direct match
            if col.lower() in text.lower():
                found.append(col)
                continue
                
            # Fuzzy match word-by-word or whole phrase?
            # Let's check if the column name is similar to any part of the text
            # This is complex efficiently. Simplified: check if column name is similar to any word in text?
            # Or use process.extractOne against the whole sentence? No.
            
            # Let's try matching the column name against the text
            # But 'age' might match 'page' or 'usage'. 'Gender' matches 'gender'.
            # We can use fuzz.partial_ratio
            ratio = fuzz.partial_ratio(col.lower(), text.lower())
            if ratio >= self.match_threshold:
                if col not in found:
                    found.append(col)
        
        return found

    def _find_truth(self, var1, var2, ground_truth):
        """
        Looks up relationship in ground truth.
        """
        # 1. Check Correlations
        correlations = ground_truth.get('correlations', [])
        for corr in correlations:
            if (corr['var1'] == var1 and corr['var2'] == var2) or \
               (corr['var1'] == var2 and corr['var2'] == var1):
                return corr
        
        # 2. Check Group Differences (T-tests/ANOVA)
        group_diffs = ground_truth.get('group_differences', [])
        for diff in group_diffs:
            if (diff['var1'] == var1 and diff['var2'] == var2) or \
               (diff['var1'] == var2 and diff['var2'] == var1):
                return diff
                
        # 3. Check Categorical Associations (Chi-Square)
        cat_assocs = ground_truth.get('categorical_associations', [])
        for assoc in cat_assocs:
            if (assoc['var1'] == var1 and assoc['var2'] == var2) or \
               (assoc['var1'] == var2 and assoc['var2'] == var1):
                return assoc
                
        return None

    def _validate_metadata(self, text, ground_truth, claim_result):
        """
        Validates metadata claims like sample size.
        """
        # Extract number from text
        params = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        if not params:
             return claim_result
             
        # Check against sample size in summary
        summary = ground_truth.get('summary', {}).get('stats', {})
        # Assuming sample size is consistent across vars, pick one
        if summary:
            first_var = list(summary.keys())[0]
            count = summary[first_var].get('count', 0)
            
            # Check if any extracted number matches count with some tolerance
            for p in params:
                try:
                    val = float(p)
                    if abs(val - count) < 5: # Tolerance of 5
                        claim_result["status"] = "VALID"
                        claim_result["reason"] = f"Valid sample size (approx {int(val)})"
                        return claim_result
                except:
                    continue
                    
        claim_result["status"] = "UNVERIFIED"
        claim_result["reason"] = "Could not verify sample size against ground truth"
        return claim_result

    def _validate_descriptive_stats(self, text, variable, ground_truth, claim_result):
        """
        Validates descriptive stats for a single variable.
        """
        summary = ground_truth.get('summary', {}).get('stats', {}).get(variable, {})
        if not summary:
            return claim_result
            
        text_lower = text.lower()
        
        # Extract numbers
        params = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        numbers = [float(p) for p in params]
        
        # Check Mean/Central Tendency
        if any(keyword in text_lower for keyword in ["mean", "average", "centered around", "typical"]):
            mean_val = summary.get('mean')
            for num in numbers:
                if mean_val and abs(num - mean_val) / (abs(mean_val) + 0.001) < 0.1: # 10% error margin
                    claim_result["status"] = "VALID"
                    claim_result["reason"] = f"Mean/Center of {variable} is approx {num}"
                    return claim_result
        
        # Check Range/Outliers
        if any(keyword in text_lower for keyword in ["range", "vary", "variability", "outlier", "minimum", "maximum"]):
            min_val = summary.get('min')
            max_val = summary.get('max')
            # If text contains min and max
            matched_min = False
            matched_max = False
            
            for num in numbers:
                if min_val and abs(num - min_val) / (abs(min_val) + 0.001) < 0.1:
                    matched_min = True
                    # If explicitly mentioned as outlier/minimum
                    if "outlier" in text_lower or "minimum" in text_lower:
                         claim_result["status"] = "VALID"
                         claim_result["reason"] = f"Minimum/Outlier {num} for {variable} verified"
                         return claim_result

                if max_val and abs(num - max_val) / (abs(max_val) + 0.001) < 0.1:
                    matched_max = True
                    if "outlier" in text_lower or "maximum" in text_lower:
                         claim_result["status"] = "VALID"
                         claim_result["reason"] = f"Maximum/Outlier {num} for {variable} verified"
                         return claim_result
            
            if matched_min or matched_max:
                 claim_result["status"] = "VALID"
                 claim_result["reason"] = f"Range/Limits for {variable} verified"
                 return claim_result
                 
            # Check if they mention standard deviation
            std_val = summary.get('std')
            for num in numbers:
                if std_val and abs(num - std_val) / (abs(std_val) + 0.001) < 0.1:
                    claim_result["status"] = "VALID"
                    claim_result["reason"] = f"Standard deviation for {variable} verified"
                    return claim_result

        # Check Median / Percentiles
        if "median" in text_lower or "50%" in text_lower or "middle" in text_lower:
             p50 = summary.get('50%')
             for num in numbers:
                if p50 and abs(num - p50) / (abs(p50) + 0.001) < 0.1:
                    claim_result["status"] = "VALID"
                    claim_result["reason"] = f"Median {variable} verified"
                    return claim_result
                    
        return claim_result
