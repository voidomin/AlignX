# Example protein sets for quick testing

# GPCR Channelrhodopsins (from user's original project)
gpcr_channelrhodopsins = [
    "3UG9",  # Closed state channelrhodopsin
    "4YZI",  # Blue-shifted mutant
    "7E6X",  # 4ms time-resolved structure
    "7X86",  # PloI4-F124L complex
    "7E6Y",  # 1-microsecond structure
]

# Hemoglobins (small test set)
hemoglobins = [
    "1A3N",  # Human hemoglobin
    "1HDA",  # Human deoxyhemoglobin
    "1GZX",  # Human carbonmonoxy hemoglobin
]

# Lysozymes (common enzyme family)
lysozymes = [
    "1LYZ",  # Hen egg-white lysozyme
    "2LYZ",  # Bacteriophage T4 lysozyme
    "3LYZ",  # Human lysozyme
]

# Kinases (diverse enzyme family)
kinases = [
    "1ATP",  # CAMP-dependent protein kinase
    "3PY3",  # AKT1 kinase
    "1M17",  # CDK2 kinase
]

# All example sets
EXAMPLES = {
    "GPCR Channelrhodopsins": gpcr_channelrhodopsins,
    "Hemoglobins": hemoglobins,
    "Lysozymes": lysozymes,
    "Kinases": kinases,
}
