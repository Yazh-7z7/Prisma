import pandas as pd
import numpy as np
from scipy import stats
import logging

class StatisticalEngine:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.StatisticalEngine")
        self.significance_level = config['statistics']['significance_level']
        self.thresholds = config['statistics']['effect_size_thresholds']

    def analyze_dataset(self, df):
        """
        Runs a complete statistical analysis on the dataset.
        Returns a dictionary of findings.
        """
        self.logger.info("Starting statistical analysis...")
        
        # Validate input
        if df is None or df.empty:
            self.logger.warning("Empty or None dataframe provided")
            return {
                "summary": {"stats": {}, "dtypes": {}},
                "correlations": [],
                "group_differences": [],
                "categorical_associations": []
            }
        
        if len(df.columns) == 0:
            self.logger.warning("Dataframe has no columns")
            return {
                "summary": {"stats": {}, "dtypes": {}},
                "correlations": [],
                "group_differences": [],
                "categorical_associations": []
            }
        
        analysis_results = {
            "summary": self._get_summary_stats(df),
            "correlations": self._calculate_correlations(df),
            "group_differences": self._detect_group_differences(df),
            "categorical_associations": self._detect_categorical_associations(df)
        }
        
        self.logger.info("Statistical analysis complete.")
        return analysis_results

    def _get_summary_stats(self, df):
        """
        Basic summary statistics.
        """
        summary = df.describe().to_dict()
        # Add data types
        dtypes = df.dtypes.apply(lambda x: str(x)).to_dict()
        
        # Add categorical summary (counts)
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            if col not in summary:
                summary[col] = df[col].value_counts().to_dict()
                
        return {"stats": summary, "dtypes": dtypes}

    def _calculate_correlations(self, df):
        """
        Calculates Pearson and Spearman correlations.
        Filters by significance and strength.
        """
        numeric_df = df.select_dtypes(include=[np.number])
        correlations = []
        
        columns = numeric_df.columns
        n = len(columns)
        
        for i in range(n):
            for j in range(i + 1, n):
                col1 = columns[i]
                col2 = columns[j]
                
                # Drop NaNs pairwise
                temp_df = numeric_df[[col1, col2]].dropna()
                if len(temp_df) < 2:
                    continue
                
                # Check for constant values (variance = 0) which causes errors in correlation
                if temp_df[col1].std() == 0 or temp_df[col2].std() == 0:
                    self.logger.debug(f"Skipping {col1} vs {col2}: constant values detected")
                    continue

                try:
                    # Pearson
                    r_p, p_p = stats.pearsonr(temp_df[col1], temp_df[col2])
                    
                    # Spearman
                    r_s, p_s = stats.spearmanr(temp_df[col1], temp_df[col2])
                except (ValueError, RuntimeWarning) as e:
                    self.logger.warning(f"Correlation calculation failed for {col1} vs {col2}: {e}")
                    continue
                
                # Determine if significant
                is_significant = (p_p < self.significance_level) or (p_s < self.significance_level)
                
                if is_significant:
                    strength = self._categorize_strength(max(abs(r_p), abs(r_s)))
                    if strength != "negligible":
                        correlations.append({
                            "var1": col1,
                            "var2": col2,
                            "pearson": {"r": r_p, "p": p_p},
                            "spearman": {"r": r_s, "p": p_s},
                            "strength": strength,
                            "direction": "positive" if r_p > 0 else "negative",
                            "type": "correlation"
                        })
                        
        return correlations

    def _detect_group_differences(self, df):
        """
        Detects significant differences in numerical variables across groups (categorical variables).
        Uses T-test (for 2 groups) and ANOVA (for >2 groups).
        """
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns
        # Treat numeric cols with few unique values as categorical candidates? For now strict types.
        
        differences = []
        
        for num_col in numeric_cols:
            for cat_col in categorical_cols:
                groups = df.groupby(cat_col)[num_col]
                group_names = df[cat_col].unique()
                group_names = [g for g in group_names if pd.notna(g)]
                
                if len(group_names) < 2:
                    continue
                
                # Safely get group data with error handling
                group_data = []
                for g in group_names:
                    try:
                        group_vals = groups.get_group(g).dropna()
                        if len(group_vals) > 1:  # Need at least 2 values for statistical test
                            group_data.append(group_vals)
                    except KeyError:
                        # Group doesn't exist, skip
                        continue
                
                if len(group_data) < 2:
                    continue

                test_name = ""
                p_val = 1.0
                stat = 0.0
                
                try:
                    if len(group_data) == 2:
                        # T-test
                        if len(group_data[0]) < 2 or len(group_data[1]) < 2:
                            continue
                        stat, p_val = stats.ttest_ind(group_data[0], group_data[1], equal_var=False)
                        test_name = "t-test"
                    else:
                        # ANOVA
                        stat, p_val = stats.f_oneway(*group_data)
                        test_name = "anova"
                except (ValueError, RuntimeWarning) as e:
                    self.logger.warning(f"Statistical test failed for {num_col} by {cat_col}: {e}")
                    continue
                
                if p_val < self.significance_level:
                    # Calculate Cohens d or Eta squared for strength?
                    # Simplified strength based on p-value for now, or just mark as significant.
                    strength = "significant" if p_val < 0.01 else "moderate"
                    
                    # Determine direction (which group is higher?)
                    means = df.groupby(cat_col)[num_col].mean().to_dict()
                    highest_group = max(means, key=means.get)
                    lowest_group = min(means, key=means.get)
                    
                    differences.append({
                        "var1": cat_col,
                        "var2": num_col,
                        "test": test_name,
                        "p_value": p_val,
                        "stat": stat,
                        "strength": strength,
                        "direction": f"{highest_group} > {lowest_group}",
                        "details": means,
                        "type": "group_difference"
                    })
        return differences

    def _detect_categorical_associations(self, df):
        """
        Detects associations between two categorical variables using Chi-Square test.
        """
        categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns
        associations = []
        
        n = len(categorical_cols)
        for i in range(n):
            for j in range(i + 1, n):
                col1 = categorical_cols[i]
                col2 = categorical_cols[j]
                
                contingency_table = pd.crosstab(df[col1], df[col2])
                
                # Check if table is valid (at least 2x2 and has sufficient data)
                if contingency_table.shape[0] < 2 or contingency_table.shape[1] < 2:
                    continue
                if contingency_table.sum().sum() < 2:  # Need at least 2 observations
                    continue
                
                try:
                    chi2, p, dof, expected = stats.chi2_contingency(contingency_table)
                    
                    # Check for invalid p-value (NaN or inf)
                    if not np.isfinite(p):
                        continue
                    
                    if p < self.significance_level:
                        # Cramer's V for strength
                        n_obs = contingency_table.sum().sum()
                        min_dim = min(contingency_table.shape) - 1
                        cv = np.sqrt(chi2 / (n_obs * min_dim)) if min_dim > 0 and n_obs > 0 else 0
                        
                        strength = self._categorize_strength(cv)
                        
                        if strength != "negligible":
                            associations.append({
                                "var1": col1,
                                "var2": col2,
                                "test": "chi-square",
                                "p_value": p,
                                "cramers_v": cv,
                                "strength": strength,
                                "direction": "associated", # Chi-square doesn't have direction in simple terms
                                "type": "categorical_association"
                            })
                except (ValueError, RuntimeWarning) as e:
                    self.logger.warning(f"Chi-square failed for {col1} vs {col2}: {e}")
                    continue
                    
        return associations

    def _categorize_strength(self, r_value):
        """
        Categorizes correlation strength.
        Maps config keys (large/medium/small) to strength labels (strong/moderate/weak).
        """
        abs_r = abs(r_value)
        if abs_r >= self.thresholds.get('large', 0.8):
            return "strong"
        elif abs_r >= self.thresholds.get('medium', 0.5):
            return "moderate"
        elif abs_r >= self.thresholds.get('small', 0.2):
            return "weak"
        else:
            return "negligible"
