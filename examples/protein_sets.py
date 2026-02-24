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

# Immunoglobulins (antibody fold conservation)
immunoglobulins = [
    "1IGT",  # Mouse IgG1
    "1HZH",  # Human IgG1
    "1IGY",  # Human IgE
]

# Serine Proteases (catalytic triad conservation)
serine_proteases = [
    "1A0J",  # Human trypsin
    "1TRN",  # Bovine trypsinogen
    "3TGI",  # Trypsin-BPTI complex
]

# Cytochrome P450s (drug metabolism enzymes)
cytochrome_p450s = [
    "1OG5",  # CYP2C9 (warfarin metabolism)
    "2HI4",  # CYP2A6 (nicotine metabolism)
    "3E4E",  # CYP3A4 (major drug metabolizer)
]

# Insulin Variants (hormone conformational changes)
insulin_variants = [
    "4INS",  # Porcine insulin (classic structure)
    "1A7F",  # Human insulin hexamer
    "1EV3",  # Insulin lispro (rapid-acting analog)
]

# COVID-19 Spike RBD (SARS-CoV-2 receptor binding)
covid_spike_rbd = [
    "6M0J",  # SARS-CoV-2 RBD bound to ACE2
    "7BNN",  # Neutralizing antibody complex
    "7KMS",  # Beta variant RBD
]

# Fluorescent Proteins (bioimaging workhorses)
fluorescent_proteins = [
    "1EMA",  # GFP (Green Fluorescent Protein)
    "2H5Q",  # mCherry (Red Fluorescent Protein)
    "1YFP",  # YFP (Yellow Fluorescent Protein)
]

# All example sets
EXAMPLES = {
    "GPCR Channelrhodopsins": gpcr_channelrhodopsins,
    "Hemoglobins": hemoglobins,
    "Lysozymes": lysozymes,
    "Kinases": kinases,
    "Immunoglobulins": immunoglobulins,
    "Serine Proteases": serine_proteases,
    "Cytochrome P450s": cytochrome_p450s,
    "Insulin Variants": insulin_variants,
    "COVID-19 Spike RBD": covid_spike_rbd,
    "Fluorescent Proteins": fluorescent_proteins,
}
