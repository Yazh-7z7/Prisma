import logging
from fuzzywuzzy import process, fuzz
import re

class Validator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.Validator")
        self.match_threshold = config['validation']['fuzzy_match_threshold'] * 100

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
        text = claim.get('original_text', '')
        if not text:
            return {
                "claim": claim,
                "extracted_vars": [],
                "status": "UNVERIFIED",
                "reason": "No text found in claim"
            }
        
        # Try to find variables mentioned in the text
        mentioned_vars = self._extract_variables(text, df_columns)

        # NEW: HALLUCINATION_VARIABLE check
        # Catches ghost variables — column names the LLM invented that don't exist in the dataset.
        ghost_vars = self._detect_ghost_variables(text, df_columns)
        if ghost_vars:
            return {
                "claim": claim,
                "extracted_vars": mentioned_vars,
                "status": "HALLUCINATION_VARIABLE",
                "reason": f"Claim references non-existent variable(s): {', '.join(ghost_vars)}"
            }
        
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
            
        # Addition 2: now that we have ground truth, compute statistically grounded confidence
        # Apply to ALL outcomes below (DIRECTION, MAGNITUDE, VALID) since all have truth data
        claim_result['claim'] = dict(claim_result['claim'])
        claim_result['claim']['confidence_score'] = self._compute_confidence(truth)

        # 3. Check direction and strength
        # Simple check: does direction match?
        claimed_direction = claim.get('direction', 'unknown')
        true_direction = truth['direction']
        
        if claimed_direction != "unknown" and claimed_direction != true_direction:
            claim_result["status"] = "HALLUCINATION_DIRECTION"
            claim_result["reason"] = f"Claimed {claimed_direction}, but actually {true_direction}"
            claim_result['ground_truth'] = truth
            return claim_result

        # NEW: HALLUCINATION_MAGNITUDE check
        magnitude_result = self._check_magnitude(claim, truth)
        if magnitude_result:
            claim_result["status"] = "HALLUCINATION_MAGNITUDE"
            claim_result["reason"] = magnitude_result
            claim_result['ground_truth'] = truth
            return claim_result

        # If we pass these checks, it's valid (or at least plausible)
        claim_result["status"] = "VALID"
        claim_result["reason"] = "Relationship confirmed by statistics"
        claim_result['ground_truth'] = truth
        
        return claim_result

    def _compute_confidence(self, truth):
        """
        NEW Addition 2: Computes a statistically grounded confidence score
        from the ground truth instead of using arbitrary keyword-based values.

        Formula:
          - Primary signal: 1 - p_value
            (lower p-value = higher statistical confidence)
          - Secondary signal: |correlation| scaled to 0-1
            (stronger effect size = higher confidence)
          - Final score = weighted average: 60% p-value signal + 40% effect size
          - Clamped to [0.01, 0.99] and rounded to 2 decimal places

        Handles both flat keys (p_value, correlation) and nested
        Pearson/Spearman structure from the statistical engine.
        """
        try:
            p_value = None
            correlation = None

            # --- Try nested Pearson structure first (from statistical_engine.py) ---
            pearson = truth.get('pearson', None)
            if pearson:
                p_value = pearson.get('p', None)
                correlation = pearson.get('r', None)

            # --- Fall back to flat keys ---
            if p_value is None:
                p_value = truth.get('p_value', None)
            if correlation is None:
                correlation = truth.get('correlation', None)

            p_signal = None
            r_signal = None

            if p_value is not None:
                try:
                    p_val = float(p_value)
                    p_val = max(0.0, min(1.0, p_val))
                    p_signal = 1.0 - p_val
                except (TypeError, ValueError):
                    pass

            if correlation is not None:
                try:
                    r_signal = min(abs(float(correlation)), 1.0)
                except (TypeError, ValueError):
                    pass

            # Weighted combination
            if p_signal is not None and r_signal is not None:
                score = 0.6 * p_signal + 0.4 * r_signal
            elif p_signal is not None:
                score = p_signal
            elif r_signal is not None:
                score = r_signal
            else:
                return 0.5  # No statistical data available

            return round(max(0.01, min(0.99, score)), 2)

        except Exception:
            return 0.5

    def _detect_ghost_variables(self, text, df_columns):
        """
        NEW: Detects variable names in the claim that do not exist in the dataset.
        These are 'ghost variables' — names hallucinated by the LLM.

        Strategy: look for capitalized words that don't match any real column
        name AND are not substrings of any real column name AND are not common
        English or statistical terms.
        Returns a list of suspected ghost variable names (empty list if none found).
        """
        ghost_vars = []

        # Convert to plain list to avoid pandas Index ambiguity
        columns_list = list(df_columns)
        if not columns_list:
            return ghost_vars

        candidates = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)

        # Common English and statistical words to ignore
        stopwords = {
            "The", "This", "There", "In", "A", "An", "It", "If", "Is", "As",
            "For", "With", "That", "These", "Those", "When", "Between", "And",
            "Or", "Of", "To", "From", "By", "On", "At", "Are", "Has", "Have",
            "Higher", "Lower", "Positive", "Negative", "Strong", "Weak", "No",
            "Moderate", "Significant", "Relationship", "Correlation", "Dataset",
            # Statistical method names — not column names
            "Pearson", "Spearman", "Kendall", "Chi", "Anova", "Ttest",
            "Cramer", "Cramers", "Fisher", "Shapiro", "Wilcoxon", "Mann",
            "Whitney", "Kruskal", "Wallis", "Bonferroni", "Tukey",
            # Common data description words
            "Mean", "Median", "Mode", "Range", "Distribution", "Variance",
            "Standard", "Deviation", "Outlier", "Trend", "Pattern", "Analysis",
            "Value", "Values", "Feature", "Features", "Variable", "Variables",
            "Increase", "Decrease", "Associated", "Suggests", "Indicates",
            "Patients", "People", "Individuals", "Group", "Groups", "Data",
            "Table", "Column", "Row", "Sample", "Population", "Study",
            "Effect", "Size", "Score", "Rate", "Risk", "Index", "Level"
        }

        col_names_lower = [c.lower() for c in columns_list]

        # Also build a set of all subwords from column names
        # e.g. "BloodPressure" → {"blood", "pressure"}
        col_subwords = set()
        for col in columns_list:
            # Split camelCase and regular words
            parts = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+', col)
            for part in parts:
                col_subwords.add(part.lower())

        for candidate in candidates:
            if candidate in stopwords:
                continue
            candidate_lower = candidate.lower()

            # Skip if it's a subword of any real column name
            if candidate_lower in col_subwords:
                continue

            # Skip if it directly matches any real column
            if candidate_lower in col_names_lower:
                continue

            # Skip if it fuzzy-matches any real column above threshold
            ratio = max(
                fuzz.ratio(candidate_lower, col.lower())
                for col in columns_list
            )
            if ratio >= 70:
                continue

            ghost_vars.append(candidate)

        return ghost_vars

    def _check_magnitude(self, claim, truth):
        """
        NEW: Checks if the claimed strength/magnitude matches the actual
        statistical strength. Returns an error string if there's a mismatch,
        or None if the magnitude is acceptable.

        Strength thresholds (based on Cohen's conventions for correlation):
            weak:     |r| < 0.3
            moderate: 0.3 <= |r| < 0.6
            strong:   |r| >= 0.6
        """
        claimed_strength = claim.get('strength', 'unknown')
        if claimed_strength == 'unknown':
            return None  # No strength claim made — nothing to check

        # Get actual correlation value from ground truth
        actual_r = truth.get('correlation', None)
        if actual_r is None:
            return None  # Can't check magnitude without a correlation value

        abs_r = abs(actual_r)

        # Determine actual strength bucket
        if abs_r < 0.3:
            actual_strength = "weak"
        elif abs_r < 0.6:
            actual_strength = "moderate"
        else:
            actual_strength = "strong"

        # Only flag if there's a meaningful mismatch
        # (e.g. claimed "strong" but actually "weak" — skip "moderate" vs "weak" as borderline)
        serious_mismatch = (
            (claimed_strength == "strong" and actual_strength == "weak") or
            (claimed_strength == "weak" and actual_strength == "strong")
        )

        if serious_mismatch:
            return (
                f"Claimed '{claimed_strength}' relationship but actual |r|={abs_r:.3f} "
                f"indicates '{actual_strength}' relationship"
            )

        return None  # Magnitude is acceptable

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
        if summary and len(summary) > 0:
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
                except (ValueError, TypeError):
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
        
        # Extract numbers with error handling
        params = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        numbers = []
        for p in params:
            try:
                numbers.append(float(p))
            except ValueError:
                # Skip non-numeric matches
                continue
        
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
