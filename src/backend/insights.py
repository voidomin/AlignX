class InsightsGenerator:
    """
    Generates automated insights and "smart captions" for structural analysis results.
    """

    def __init__(self, config):
        self.config = config
        self._analyzer = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            from src.backend.rmsd_analyzer import RMSDAnalyzer

            self._analyzer = RMSDAnalyzer(self.config)
        return self._analyzer

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

        rmsd_df = results.get("rmsd_df")
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
                insights.append(
                    f"✅ **High Homogeneity**: The dataset is structurally very similar (Avg RMSD: {avg_rmsd:.2f} Å)."
                )
            elif avg_rmsd > 5.0:
                insights.append(
                    f"⚠️ **High Diversity**: significant structural variation observed (Avg: {avg_rmsd:.2f} Å)."
                )
            else:
                insights.append(
                    f"ℹ️ **Moderate Diversity**: Structures show expected variation (Avg: {avg_rmsd:.2f} Å)."
                )

            # 2. Best Match (Lowest RMSD)
            # Use dataframe with INF on diagonal to find minimum non-zero value
            min_mask_df = rmsd_df.copy()
            np.fill_diagonal(min_mask_df.values, np.inf)

            min_val = min_mask_df.min().min()
            min_pair = min_mask_df.stack().idxmin()  # Returns (Row, Col)

            insights.append(
                f"🏆 **Best Match**: `{min_pair[0]}` and `{min_pair[1]}` are nearly identical ({min_val:.2f} Å)."
            )

            # 3. Worst Match (Highest RMSD)
            # Use dataframe with -1 on diagonal to find maximum (masking self-comparison)
            max_mask_df = rmsd_df.copy()
            np.fill_diagonal(max_mask_df.values, -1.0)

            max_val = max_mask_df.max().max()
            max_pair = max_mask_df.stack().idxmax()

            if max_val > 5.0:
                insights.append(
                    f"↔️ **Most Divergent**: `{max_pair[0]}` and `{max_pair[1]}` differ significantly ({max_val:.2f} Å)."
                )

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
                insights.append(
                    f"🚩 **Outlier Detected**: **{pid}** is a structural outlier with average RMSD **{val:.2f} Å** (> {threshold:.2f} Å threshold)."
                )

        # 5. Ligand Insights
        # Check ligand analysis results if available
        if "ligand_analysis" in results:
            ligand_data = results["ligand_analysis"]
            # Count total ligands
            total_ligands = sum(len(l) for l in ligand_data.values())
            if total_ligands > 0:
                # Find most common ligand
                all_ligand_names = []
                for l_list in ligand_data.values():
                    all_ligand_names.extend([l["name"] for l in l_list])

                from collections import Counter

                common = Counter(all_ligand_names).most_common(1)

                insights.append(
                    f"💊 **Ligand Analysis**: Found {total_ligands} ligands across structures. Most common: **{common[0][0]}** ({common[0][1]} occurrences)."
                )

        # 6. Cluster Insights
        # Using a default threshold to glimpse structure
        clusters = self.analyzer.identify_clusters(rmsd_df, threshold=2.0)
        if len(clusters) > 1:
            insights.append(
                f"🔍 **Structural Families**: At 2.0 Å threshold, structures fall into **{len(clusters)} distinct clusters**."
            )

        # 7. Structural Confidence (TM-Score/GDT-TS)
        q_metrics = results.get("quality_metrics")
        if q_metrics:
            avg_tm = np.mean([m["tm_score"] for m in q_metrics.values()])
            if avg_tm > 0.7:
                insights.append(
                    f"🛡️ **High Confidence**: Average TM-score of {avg_tm:.3f} indicates a highly reliable structural consensus."
                )
            elif avg_tm < 0.5:
                insights.append(
                    f"⚠️ **Low Confidence**: Average TM-score of {avg_tm:.3f} suggests the structures may belong to different folds or have poor alignment."
                )

            # Identify highest and lowest quality
            sorted_q = sorted(
                q_metrics.items(), key=lambda x: x[1]["tm_score"], reverse=True
            )
            best_id, best_m = sorted_q[0]
            worst_id, worst_m = sorted_q[-1]

            if best_m["tm_score"] > 0.9:
                insights.append(
                    f"🌟 **Top Fit**: `{best_id}` is the most representative structure (TM-score: {best_m['tm_score']:.3f})."
                )
            if worst_m["tm_score"] < 0.4:
                insights.append(
                    f"📉 **Weak Fit**: `{worst_id}` shows significant structural divergence (TM-score: {worst_m['tm_score']:.3f})."
                )

        return insights
