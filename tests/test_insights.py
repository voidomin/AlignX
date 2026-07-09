from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.backend.insights import InsightsGenerator


@pytest.fixture
def generator(mock_config):
    return InsightsGenerator(mock_config)


class TestAnalyzerProperty:
    def test_lazily_constructs_rmsd_analyzer(self, generator):
        from src.backend.rmsd_analyzer import RMSDAnalyzer

        assert generator._analyzer is None
        analyzer = generator.analyzer
        assert isinstance(analyzer, RMSDAnalyzer)
        assert generator.analyzer is analyzer  # cached, not rebuilt


class TestGenerateInsights:
    def test_empty_results_returns_empty_list(self, generator):
        assert generator.generate_insights({}) == []

    def test_missing_rmsd_df_returns_placeholder(self, generator):
        result = generator.generate_insights({"rmsd_df": None})
        assert result == ["RMSD data not available for insights."]

    def test_aggregates_all_sub_insights_in_order(self, generator):
        for name, value in [
            ("_get_rmsd_summary", ["rmsd"]),
            ("_get_outlier_insights", ["outlier"]),
            ("_get_ligand_insights", ["ligand"]),
            ("_get_binding_pocket_insights", ["pocket"]),
            ("_get_clustering_insights", ["cluster"]),
            ("_get_quality_metrics_insights", ["quality"]),
            ("_get_ramachandran_insights", ["rama"]),
        ]:
            setattr(generator, name, MagicMock(return_value=value))

        result = generator.generate_insights({"rmsd_df": pd.DataFrame()})

        assert result == [
            "rmsd",
            "outlier",
            "ligand",
            "pocket",
            "cluster",
            "quality",
            "rama",
        ]


class TestGetRmsdSummary:
    def test_high_homogeneity_and_best_match(self, generator):
        df = pd.DataFrame(
            [[0.0, 1.0], [1.0, 0.0]], index=["A", "B"], columns=["A", "B"]
        )
        insights = generator._get_rmsd_summary(df)
        assert any("High Homogeneity" in i for i in insights)
        assert any("Best Match" in i for i in insights)
        assert not any("Most Divergent" in i for i in insights)

    def test_high_diversity_and_most_divergent(self, generator):
        df = pd.DataFrame(
            [[0.0, 8.0], [8.0, 0.0]], index=["A", "B"], columns=["A", "B"]
        )
        insights = generator._get_rmsd_summary(df)
        assert any("High Diversity" in i for i in insights)
        assert any("Most Divergent" in i for i in insights)

    def test_moderate_diversity(self, generator):
        df = pd.DataFrame(
            [[0.0, 3.5], [3.5, 0.0]], index=["A", "B"], columns=["A", "B"]
        )
        insights = generator._get_rmsd_summary(df)
        assert any("Moderate Diversity" in i for i in insights)

    def test_single_structure_returns_empty(self, generator):
        df = pd.DataFrame([[0.0]], index=["A"], columns=["A"])
        assert generator._get_rmsd_summary(df) == []


class TestGetOutlierInsights:
    def test_flags_structural_outlier(self, generator):
        df = pd.DataFrame(
            {
                "A": [0.0, 1.0, 1.2, 0.9, 15.0],
                "B": [1.0, 0.0, 1.1, 0.8, 15.0],
                "C": [1.2, 1.1, 0.0, 1.0, 15.0],
                "D": [0.9, 0.8, 1.0, 0.0, 15.0],
                "E": [15.0, 15.0, 15.0, 15.0, 0.0],
            },
            index=["A", "B", "C", "D", "E"],
        )
        mean_rmsds = df.mean()
        threshold = mean_rmsds.mean() + 1.5 * mean_rmsds.std()
        expected_outliers = set(mean_rmsds[mean_rmsds > threshold].index)
        assert "E" in expected_outliers  # sanity: the fixture actually has an outlier

        insights = generator._get_outlier_insights(df)

        flagged = {pid for pid in expected_outliers if any(pid in i for i in insights)}
        assert flagged == expected_outliers
        assert any("Outlier Detected" in i for i in insights)

    def test_no_outliers_when_uniform(self, generator):
        df = pd.DataFrame({"A": [0.0, 1.0], "B": [1.0, 0.0]}, index=["A", "B"])
        assert generator._get_outlier_insights(df) == []


class TestGetLigandInsights:
    def test_reports_total_and_most_common(self, generator):
        results = {
            "ligand_analysis": {
                "P1": [{"name": "ATP"}, {"name": "ATP"}],
                "P2": [{"name": "GTP"}],
            }
        }
        insights = generator._get_ligand_insights(results)
        assert len(insights) == 1
        assert "3 total ligands" in insights[0]
        assert "ATP" in insights[0]

    def test_missing_key_returns_empty(self, generator):
        assert generator._get_ligand_insights({}) == []

    def test_zero_ligands_returns_empty(self, generator):
        assert generator._get_ligand_insights({"ligand_analysis": {"P1": []}}) == []


class TestGetBindingPocketInsights:
    def test_missing_key_returns_empty(self, generator):
        assert generator._get_binding_pocket_insights({}) == []

    def test_empty_dataframe_returns_empty(self, generator):
        results = {"ligand_pocket_similarity": pd.DataFrame()}
        assert generator._get_binding_pocket_insights(results) == []

    def test_single_ligand_returns_empty(self, generator):
        df = pd.DataFrame([[1.0]], index=["A"], columns=["A"])
        results = {"ligand_pocket_similarity": df}
        assert generator._get_binding_pocket_insights(results) == []

    def test_similar_pair_flagged_with_caveat(self, generator):
        df = pd.DataFrame(
            [[1.0, 0.75], [0.75, 1.0]],
            index=["4HHB:HEM_A_1", "2HHB:HEM_A_1"],
            columns=["4HHB:HEM_A_1", "2HHB:HEM_A_1"],
        )
        insights = generator._get_binding_pocket_insights(
            {"ligand_pocket_similarity": df}
        )
        assert any("Similar Binding Pockets" in i for i in insights)
        assert any("4HHB:HEM_A_1" in i and "2HHB:HEM_A_1" in i for i in insights)
        assert any("residue *names*" in i for i in insights)
        assert not any("Divergent Binding Pockets" in i for i in insights)

    def test_divergent_pair_flagged_with_caveat(self, generator):
        df = pd.DataFrame(
            [[1.0, 0.1], [0.1, 1.0]],
            index=["4HHB:HEM_A_1", "1CRN:XXX_A_1"],
            columns=["4HHB:HEM_A_1", "1CRN:XXX_A_1"],
        )
        insights = generator._get_binding_pocket_insights(
            {"ligand_pocket_similarity": df}
        )
        assert any("Divergent Binding Pockets" in i for i in insights)
        assert any("residue *names*" in i for i in insights)
        assert not any("Similar Binding Pockets" in i for i in insights)

    def test_neither_threshold_crossed_returns_empty_with_no_caveat_noise(
        self, generator
    ):
        df = pd.DataFrame(
            [[1.0, 0.4], [0.4, 1.0]], index=["A", "B"], columns=["A", "B"]
        )
        assert (
            generator._get_binding_pocket_insights({"ligand_pocket_similarity": df})
            == []
        )


class TestGetClusteringInsights:
    def test_multiple_clusters_reported(self, generator):
        generator._analyzer = MagicMock()
        generator._analyzer.identify_clusters.return_value = [["A"], ["B", "C"]]

        insights = generator._get_clustering_insights(pd.DataFrame())

        assert any("2 distinct clusters" in i for i in insights)

    def test_single_cluster_returns_empty(self, generator):
        generator._analyzer = MagicMock()
        generator._analyzer.identify_clusters.return_value = [["A", "B", "C"]]

        assert generator._get_clustering_insights(pd.DataFrame()) == []


class TestGetQualityMetricsInsights:
    def test_high_confidence_top_and_weak_fit(self, generator):
        results = {
            "quality_metrics": {
                "M1": {"tm_score": 0.97},
                "M2": {"tm_score": 0.9},
                "M3": {"tm_score": 0.3},
            }
        }
        insights = generator._get_quality_metrics_insights(results)
        assert any("High Confidence" in i for i in insights)
        assert any("Top Fit" in i for i in insights)
        assert any("Weak Fit" in i and "M3" in i for i in insights)

    def test_low_confidence(self, generator):
        results = {
            "quality_metrics": {
                "M1": {"tm_score": 0.4},
                "M2": {"tm_score": 0.45},
            }
        }
        insights = generator._get_quality_metrics_insights(results)
        assert any("Low Confidence" in i for i in insights)

    def test_missing_key_returns_empty(self, generator):
        assert generator._get_quality_metrics_insights({}) == []


class TestGetRamachandranInsights:
    def test_exceptional_quality_and_no_outlier_flag(self, generator):
        results = {"ramachandran_stats": {"favored_percent": 98, "outlier_count": 2}}
        insights = generator._get_ramachandran_insights(results)
        assert any("Exceptional Quality" in i for i in insights)
        assert not any("Local Geometry" in i for i in insights)

    def test_geometry_alert_and_local_geometry_outliers(self, generator):
        results = {"ramachandran_stats": {"favored_percent": 60, "outlier_count": 15}}
        insights = generator._get_ramachandran_insights(results)
        assert any("Geometry Alert" in i for i in insights)
        assert any("Local Geometry" in i and "15" in i for i in insights)

    def test_missing_key_returns_empty(self, generator):
        assert generator._get_ramachandran_insights({}) == []
