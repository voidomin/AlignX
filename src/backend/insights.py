import numpy as np
from collections import Counter
from typing import List, Dict, Any, Optional


class InsightsGenerator:
    """
    Generates automated insights and "smart captions" for structural analysis results.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._analyzer = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            from src.backend.rmsd_analyzer import RMSDAnalyzer
            self._analyzer = RMSDAnalyzer(self.config)
        return self._analyzer

    def generate_insights(self, results: Dict[str, Any]) -> List[str]:
        """
        Analyze results and return a list of textual insights.
        """
        insights = []

        if not results:
            return insights

        rmsd_df = results.get("rmsd_df")
        if rmsd_df is None:
            return ["RMSD data not available for insights."]

        # Aggregate insights from various modules
        insights.extend(self._get_rmsd_summary(rmsd_df))
        insights.extend(self._get_outlier_insights(rmsd_df))
        insights.extend(self._get_ligand_insights(results))
        insights.extend(self._get_clustering_insights(rmsd_df))
        insights.extend(self._get_quality_metrics_insights(results))
        insights.extend(self._get_ramachandran_insights(results))

        return insights

    def _get_rmsd_summary(self, rmsd_df) -> List[str]:
        """Analyze dataset homogeneity and best/worst matches."""
        insights = []
        vals = rmsd_df.values
        upper_tri = vals[np.triu_indices_from(vals, k=1)]

        if len(upper_tri) > 0:
            avg_rmsd = np.mean(upper_tri)

            if avg_rmsd < 2.0:
                insights.append(
                    f"✅ **High Homogeneity**: The dataset is structurally very similar (Avg RMSD: {avg_rmsd:.2f} Å)."
                )
            elif avg_rmsd > 5.0:
                insights.append(
                    f"⚠️ **High Diversity**: Significant structural variation observed (Avg: {avg_rmsd:.2f} Å)."
                )
            else:
                insights.append(
                    f"ℹ️ **Moderate Diversity**: Structures show expected variation (Avg: {avg_rmsd:.2f} Å)."
                )

            # Best Match
            min_mask_df = rmsd_df.copy()
            np.fill_diagonal(min_mask_df.values, np.inf)
            min_val = min_mask_df.min().min()
            min_pair = min_mask_df.stack().idxmin()
            insights.append(
                f"🏆 **Best Match**: `{min_pair[0]}` and `{min_pair[1]}` are nearly identical ({min_val:.2f} Å)."
            )

            # Worst Match
            max_mask_df = rmsd_df.copy()
            np.fill_diagonal(max_mask_df.values, -1.0)
            max_val = max_mask_df.max().max()
            max_pair = max_mask_df.stack().idxmax()
            if max_val > 5.0:
                insights.append(
                    f"↔️ **Most Divergent**: `{max_pair[0]}` and `{max_pair[1]}` differ significantly ({max_val:.2f} Å)."
                )

        return insights

    def _get_outlier_insights(self, rmsd_df) -> List[str]:
        """Detect structural outliers using Z-score logic."""
        insights = []
        mean_rmsds = rmsd_df.mean()
        dataset_mean = mean_rmsds.mean()
        dataset_std = mean_rmsds.std()

        threshold = dataset_mean + (1.5 * dataset_std)
        outliers = mean_rmsds[mean_rmsds > threshold]

        for pid, val in outliers.items():
            insights.append(
                f"🚩 **Outlier Detected**: **{pid}** is a structural outlier with average RMSD **{val:.2f} Å** (> {threshold:.2f} Å threshold)."
            )
        return insights

    def _get_ligand_insights(self, results: Dict[str, Any]) -> List[str]:
        """Analyze ligand distribution."""
        insights = []
        if "ligand_analysis" in results:
            ligand_data = results["ligand_analysis"]
            total_ligands = sum(len(lig_list) for lig_list in ligand_data.values())
            if total_ligands > 0:
                all_names = [lig["name"] for lig_list in ligand_data.values() for lig in lig_list]
                common = Counter(all_names).most_common(1)
                insights.append(
                    f"💊 **Ligand Analysis**: Found {total_ligands} total ligands. Most common: **{common[0][0]}** ({common[0][1]} occurrences)."
                )
        return insights

    def _get_clustering_insights(self, rmsd_df) -> List[str]:
        """Identify structural families."""
        insights = []
        clusters = self.analyzer.identify_clusters(rmsd_df, threshold=2.0)
        if len(clusters) > 1:
            insights.append(
                f"🔍 **Structural Families**: At 2.0 Å threshold, structures fall into **{len(clusters)} distinct clusters**."
            )
        return insights

    def _get_quality_metrics_insights(self, results: Dict[str, Any]) -> List[str]:
        """Analyze TM-score and GDT-TS."""
        insights = []
        q_metrics = results.get("quality_metrics")
        if q_metrics:
            scores = [m["tm_score"] for m in q_metrics.values()]
            avg_tm = np.mean(scores)
            
            if avg_tm > 0.7:
                insights.append(f"🛡️ **High Confidence**: Average TM-score of {avg_tm:.3f} indicates a reliable structural consensus.")
            elif avg_tm < 0.5:
                insights.append(f"⚠️ **Low Confidence**: Average TM-score of {avg_tm:.3f} suggests possible structural divergence.")

            # Best/Worst models
            sorted_q = sorted(q_metrics.items(), key=lambda x: x[1]["tm_score"], reverse=True)
            _, best_m = sorted_q[0]
            worst_id, worst_m = sorted_q[-1]

            if best_m["tm_score"] > 0.9:
                insights.append(f"🌟 **Top Fit**: A highly representative model was identified (TM-score: {best_m['tm_score']:.3f}).")
            if worst_m["tm_score"] < 0.4:
                insights.append(f"📉 **Weak Fit**: `{worst_id}` shows significant divergence (TM-score: {worst_m['tm_score']:.3f}).")
        return insights

    def _get_ramachandran_insights(self, results: Dict[str, Any]) -> List[str]:
        """Analyze protein geometry via Ramachandran plots."""
        insights = []
        r_stats = results.get("ramachandran_stats")
        if r_stats:
            favored = r_stats.get("favored_percent", 0)
            outliers = r_stats.get("outlier_count", 0)

            if favored > 95:
                insights.append(f"💎 **Exceptional Quality**: {favored:.1f}% of residues are in favored regions.")
            elif favored < 80:
                insights.append(f"⚠️ **Geometry Alert**: Low favored region percentage ({favored:.1f}%).")

            if outliers > 10:
                insights.append(f"🚩 **Local Geometry**: Found {outliers} Ramachandran outliers across structures.")
        return insights
