class InsightsGenerator:
    """
    Generates automated insights and "smart captions" for structural analysis results.
    """
    def __init__(self, config):
        self.config = config

    def generate_insights(self, results):
        """
        Analyze results and return a list of textual insights.
        
        Args:
            results (dict): The results dictionary from the pipeline.
            
        Returns:
            list: A list of strings containing insights.
        """
        insights = []
        
        if not results:
            return insights
            
        rmsd_df = results.get('rmsd_df')
        if rmsd_df is None:
            return ["RMSD data not available for insights."]

        # 1. Dataset Homogeneity
        # Upper triangle of RMSD matrix (excluding diagonal)
        import numpy as np
        vals = rmsd_df.values
        upper_tri = vals[np.triu_indices_from(vals, k=1)]
        
        if len(upper_tri) > 0:
            avg_rmsd = np.mean(upper_tri)
            min_rmsd = np.min(upper_tri)
            max_rmsd = np.max(upper_tri)
            
            if avg_rmsd < 2.0:
                insights.append(f"✅ **High Homogeneity**: The dataset is structurally very similar (Avg RMSD: {avg_rmsd:.2f} Å).")
            elif avg_rmsd > 5.0:
                insights.append(f"⚠️ **High Diversity**: significant structural variation observed (Avg: {avg_rmsd:.2f} Å).")
            else:
                insights.append(f"ℹ️ **Moderate Diversity**: Structures show expected variation (Avg: {avg_rmsd:.2f} Å).")

            # 2. Best Match (Lowest RMSD)
            # Use dataframe with INF on diagonal to find minimum non-zero value
            min_mask_df = rmsd_df.copy()
            np.fill_diagonal(min_mask_df.values, np.inf)
            
            min_val = min_mask_df.min().min()
            min_pair = min_mask_df.stack().idxmin() # Returns (Row, Col)
            
            insights.append(f"🏆 **Best Match**: `{min_pair[0]}` and `{min_pair[1]}` are nearly identical ({min_val:.2f} Å).")

            # 3. Worst Match (Highest RMSD)
            # Use dataframe with -1 on diagonal to find maximum (masking self-comparison)
            max_mask_df = rmsd_df.copy()
            np.fill_diagonal(max_mask_df.values, -1.0)
            
            max_val = max_mask_df.max().max()
            max_pair = max_mask_df.stack().idxmax()
            
            if max_val > 5.0:
                insights.append(f"↔️ **Most Divergent**: `{max_pair[0]}` and `{max_pair[1]}` differ significantly ({max_val:.2f} Å).")

        # 4. Outlier Detection
        # Calculate mean RMSD for each protein against all others
        mean_rmsds = rmsd_df.mean()
        dataset_mean = mean_rmsds.mean()
        dataset_std = mean_rmsds.std()
        
        # Threshold: > Mean + 1.5 STD
        threshold = dataset_mean + (1.5 * dataset_std)
        outliers = mean_rmsds[mean_rmsds > threshold]
        
        if not outliers.empty:
            for pid, val in outliers.items():
                insights.append(f"🚩 **Outlier Detected**: `{pid}` (Avg RMSD {val:.2f} Å) deviates from the group.")

        return insights
