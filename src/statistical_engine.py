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
                
                # Pearson
                r_p, p_p = stats.pearsonr(numeric_df[col1].dropna(), numeric_df[col2].dropna())
                
                # Spearman
                r_s, p_s = stats.spearmanr(numeric_df[col1].dropna(), numeric_df[col2].dropna())
                
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
                
                group_data = [groups.get_group(g).dropna() for g in group_names]
                # Prepare for tests (remove empty groups)
                group_data = [g for g in group_data if len(g) > 1]
                
                if len(group_data) < 2:
                    continue

                test_name = ""
                p_val = 1.0
                stat = 0.0
                
                if len(group_names) == 2:
                    # T-test
                    stat, p_val = stats.ttest_ind(group_data[0], group_data[1], equal_var=False)
                    test_name = "t-test"
                else:
                    # ANOVA
                    try:
                        stat, p_val = stats.f_oneway(*group_data)
                        test_name = "anova"
                    except Exception as e:
                        self.logger.warning(f"ANOVA failed for {num_col} by {cat_col}: {e}")
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
                try:
                    chi2, p, dof, expected = stats.chi2_contingency(contingency_table)
                    
                    if p < self.significance_level:
                        # Cramer's V for strength
                        n_obs = contingency_table.sum().sum()
                        min_dim = min(contingency_table.shape) - 1
                        cv = np.sqrt(chi2 / (n_obs * min_dim)) if min_dim > 0 else 0
                        
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
                except Exception as e:
                    self.logger.warning(f"Chi-square failed for {col1} vs {col2}: {e}")
                    
        return associations

    def _categorize_strength(self, r_value):
        """
        Categorizes correlation strength.
        """
        abs_r = abs(r_value)
        if abs_r >= self.thresholds['strong']:
            return "strong"
        elif abs_r >= self.thresholds['moderate']:
            return "moderate"
        elif abs_r >= self.thresholds['weak']:
            return "weak"
        else:
            return "negligible"
