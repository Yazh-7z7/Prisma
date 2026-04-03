import re
import logging
import json

class InsightParser:
    def __init__(self):
        self.logger = logging.getLogger("Prisma.InsightParser")

    def parse_insights(self, llm_output):
        """
        Parses LLM output into structured claims.
        Returns a list of dictionaries with keys: var1, var2, relationship, strength, direction.
        """
        self.logger.info("Parsing insights...")
        
        # Basic parsing logic: Look for "Var1 correlates with Var2" patterns
        # This is a simplified regex-based parser. In a real scenario, we might use an LLM or dependency parsing.
        
        insights = []
        
        # Validate input
        if not llm_output or not isinstance(llm_output, str):
            self.logger.warning("Empty or invalid LLM output provided")
            return insights
        
        # Split by lines or numbered lists
        lines = llm_output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Regex to catch "Var1 [relationship] Var2"
            # Very naive implementation for demonstration
            # We look for common correlation keywords
            
            # Example pattern: "Age is positively correlated with Heart Disease"
            # Example pattern: "There is a strong relationship between BMI and Diabetes"
            
            # We'll use a heuristic approach: identify variables from the text? 
            # Or just extract the whole sentence as the "claim" and try to find variable names in it later during validation.
            # A better approach for this project: return the full claim text and let the Validator try to match variables.
            
            # But the Validator needs structured vars.
            # Let's try to extract variable names if we know the dataset columns. 
            # -> We need the dataset columns passed to the parser or validator.
            # For now, we will store the raw text and do "entity extraction" in the validator or here if columns are known.
            
            # Let's assume we don't know columns here, so we return the raw claim.
            # However, the prompt asks for "numbered list", so we extract items.
            
            if re.match(r'^\d+[\.)]', line):
                clean_line = re.sub(r'^\d+[\.)]\s*', '', line)
                insights.append({
                    "original_text": clean_line,
                    "variables": [], # To be filled by Validator or advanced parsing
                    "relationship": "correlation", # Default assumption
                    "direction": "unknown",
                    "strength": "unknown",
                    "confidence_score": 0.5, # Default confidence score
                    "type": "correlation" # Default type
                })

        # Advanced: Use an LLM to parse the output into JSON if the prompt asked for JSON.
        # But for this "research system", let's try to parse English.
        
        # Let's try to refine the extraction using keywords
        for insight in insights:
            text = insight['original_text'].lower()
            
            # Fix direction detection logic
            if "positive" in text or ("increases" in text and "decreases" not in text):
                insight['direction'] = "positive"
            elif "negative" in text or "decreases" in text:
                insight['direction'] = "negative"
                
            if "strong" in text or "significant" in text:
                insight['strength'] = "strong"
                insight['confidence_score'] = 0.8  # Higher confidence for strong claims
            elif "weak" in text:
                insight['strength'] = "weak"
                insight['confidence_score'] = 0.4  # Lower confidence for weak claims
            elif "moderate" in text:
                insight['strength'] = "moderate"
                insight['confidence_score'] = 0.6  # Medium confidence for moderate claims

        self.logger.info(f"Extracted {len(insights)} potential insights.")
        return insights

    def extract_variables(self, text, columns):
        """
        Helper to find which columns are mentioned in the text.
        """
        from fuzzywuzzy import process
        
        found_vars = []
        words = text.split()
        
        # Check for direct matches
        for col in columns:
            if col.lower() in text.lower():
                found_vars.append(col)
        
        # If not enough found, try fuzzy matching words to columns
        # This is expensive and might yield false positives, use with care.
        # Simple implementation: unique set of found vars
        return list(set(found_vars))
