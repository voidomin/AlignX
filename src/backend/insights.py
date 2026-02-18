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
            
        # Placeholder logic
        stats = results.get('stats', {})
        if stats:
             insights.append(f"Average RMSD across all structures is {stats.get('mean_rmsd', 0):.2f} Å.")
             
        return insights
