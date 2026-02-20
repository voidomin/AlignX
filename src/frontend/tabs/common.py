import streamlit as st

def render_learning_card(tab_name: str) -> None:
    """
    Render a context-aware learning card for Guided Mode.
    
    Args:
        tab_name: The name of the current tab (e.g., 'Summary', 'Sequence').
    """
    if not st.session_state.get('guided_mode', False):
        return

    content = {
        "Summary": {
            "title": "🎓 Learning: Understanding Alignment Quality",
            "body": """
            - **RMSD (Root Mean Square Deviation)**: Measures the average distance between atoms. Lower is better (0.0 is perfect).
            - **Alignment Length**: How many residues were successfully matched.
            - **Sequence Identity**: % of exact amino acid matches. High identity often means similar function.
            """
        },
        "Sequence": {
            "title": "🎓 Learning: Sequence Conservation",
            "body": """
            - **Conservation Score (0-9)**:
            - **9 (Star)**: Identity. The same amino acid is present in all structures. Crucial for function.
            - **0-4**: Variable regions. These parts evolve rapidly or are less important.
            - **Tip**: Click on a residue in the table to highlight it in the 3D viewer!
            """
        },
        "Structure": {
            "title": "🎓 Learning: Structural Superposition",
            "body": """
            - **Superposition**: Rotates proteins to overlap them as best as possible.
            - **Visual Styles**:
            - **Cartoon**: Best for seeing helices and sheets.
            - **Surface**: Good for finding pockets.
            - **Controls**: Mouse Wheel to Zoom, Drag to Rotate.
            """
        },
        "Ligands": {
            "title": "🎓 Learning: Ligand Interactions",
            "body": """
            - **Ligands**: Small molecules (drugs, cofactors) bound to the protein.
            - **Interaction Similarity**:
            - **1.0**: Identical binding pockets.
            - **0.0**: Completely different binding pockets.
            - **Tip**: Use 'Pocket Comparison' to see how different proteins bind the same (or different) ligands.
            """
        },
        "Tree": {
            "title": "🎓 Learning: Phylogenetic Tree",
            "body": """
            - **Clustering**: Groups proteins by structural similarity.
            - **Branch Length**: Longer branches mean more structural difference.
            - **Clusters**: Items in the same color group are likely a sub-family.
            """
        }
    }

    if tab_name in content:
        card = content[tab_name]
        with st.container():
            st.info(f"**{card['title']}**\n\n{card['body']}")
            st.divider()

def render_help_expander(topic: str) -> None:
    """
    Render educational help expanders.
    
    Args:
        topic: The topic key (e.g., 'rmsd', 'tree', 'ligands').
    """
    helps = {
        "rmsd": {
            "title": "❓ What is RMSD & How to read this?",
            "content": """
                ### **1. What is RMSD?**
                **RMSD (Root Mean Square Deviation)** is the standard measure of structural difference between proteins. It calculates the average distance between matching atoms in two superimposed structures.
                *   **Unit**: Angstroms (Å). 1 Å = 0.1 nanometers.
                
                ### **2. How to read the Heatmap:**
                This grid compares every protein against every other protein.
                *   **🟦 Blue (Low RMSD, e.g., < 2.0 Å)**: The structures are **very similar**. They likely share the same function and evolutionary origin.
                *   **🟥 Red (High RMSD, e.g., > 2.0 Å)**: The structures are **different**. They may have diverged significantly or look completely different.
                *   **Diagonal**: Always 0.00, because a protein compared to itself has 0 difference.
            """
        },
        "rmsf": {
            "title": "❓ What is RMSF & How to read this?",
            "content": """
                ### **1. What is RMSF?**
                **RMSF (Root Mean Square Fluctuation)** measures how much each individual amino acid moves around in space.
                *   **Rigid**: Parts that don't move much (the core structure).
                *   **Flexible**: Parts that wobble or flap around (loops, tails).
                
                ### **2. How to read the Chart:**
                *   **X-Axis**: The sequence of amino acids (Position 1, 2, 3...).
                *   **Y-Axis (RMSF Å)**: How much that position moved. Higher = More Flexible.
                *   **Peaks 📈**: Identify flexible loops or disordered regions. These are often where ligands bind or interactions happen!
                *   **Valleys 📉**: The stable core of the protein.
            """
        },
        "tree": {
            "title": "❓ What is this Tree & How to read it?",
            "content": """
                ### **1. What is a Structural Tree?**
                Unlike traditional evolutionary trees based on DNA sequences, this tree groups proteins based on their **3D shape similarity** (Structural Phylogeny).
                *   **Clustering**: Proteins on the same branch are "structural siblings." They look very similar in 3D space.
                *   **Distance**: The horizontal length of the branches represents the RMSD distance. **Longer branches = distinct structures**.
                
                ### **2. Why use UPGMA?**
                UPGMA (Unweighted Pair Group Method with Arithmetic Mean) is a simple clustering algorithm that assumes a constant rate of evolution. It's great for visualizing hierarchical relationships in data.
            """
        },
        "clusters": {
            "title": "❓ What are Clusters & How to read this?",
            "content": """
                ### **1. What is Structural Clustering?**
                Clustering is a way to group proteins that are "structurally similar" into families. We use **Hierarchical Clustering (UPGMA)** based on the RMSD values.
                
                ### **2. The RMSD Threshold:**
                This is the "cutoff" distance for forming a group. 
                *   **Low Threshold (e.g., 1.5 Å)**: Only very similar proteins (nearly identical folds) will be grouped together.
                *   **High Threshold (e.g., 5.0 Å)**: Even distantly related proteins (sharing only broad structural features) will be put into the same cluster.
                
                ### **3. Why use this?**
                It helps identify sub-families within a large dataset, making it easier to see which proteins might share specific functionalities or binding properties.
            """
        },
        "superposition": {
            "title": "❓ What is Superposition & Interpretation Guide",
            "content": """
                ### **1. What is Superposition?**
                Superposition is the process of attempting to **overlap** multiple protein structures on top of each other to find the "best fit." This allows us to see exactly where they differ.
                *   **Aligned Regions**: Parts of the proteins that overlap perfectly usually have the same function.
                *   **Divergent Regions**: Parts that stick out or don't overlap are variable regions (often loops or surface areas).

                ### **2. Visualization Styles:**
                *   **Cartoon**: Simplifies the protein into ribbons (helices) and arrows (sheets). Best for seeing the overall "fold" or shape.
                *   **Stick**: Shows the bonds between atoms. Useful for seeing side-chains.
                *   **Surface**: Shows the outer "skin" of the molecule. Good for seeing pockets.
            """
        },
        "ligands": {
            "title": "❓ What are Ligands & How to read this?",
            "content": """
                ### **1. What is a Ligand?**
                A **ligand** is a small molecule (like a drug, hormone, or vitamin) that binds to a specific site on a protein to trigger a function or inhibit it. Think of it as a **key** fitting into a **lock** (the protein).
                
                ### **2. How to use this tool:**
                1.  **Select a Protein**: Choose one of your aligned structures from the dropdown.
                2.  **Select a Ligand**: Pick the specific small molecule found in that structure.
                3.  **Analyze Interactions**: Click the button to calculate which parts of the protein are "touching" the ligand.
                
                ### **3. Understanding the Results:**
                -   **3D View (Right)**: Shows the ligand (colorful sticks) inside its binding pocket.
                    -   The **Green/Blue/Red residues** represent the parts of the protein holding the ligand in place.
                -   **Interaction Table (Bottom Right)**:
                    -   **Residue**: The specific amino acid in the protein chain.
                    -   **Distance (Å)**: How close it is to the ligand. **< 3.5 Å** usually means a strong chemical bond.
                    -   **Type**: The kind of connection (e.g., *Hydrogen Bond* = strong, sticky; *Hydrophobic* = oily/greasy interaction).
            """
        }
    }
    if topic in helps:
        with st.expander(helps[topic]["title"], expanded=False):
            st.markdown(helps[topic]["content"])

def render_progress_stepper(current_step: int) -> None:
    """
    Render a visual progress stepper for the analysis workflow.
    
    Args:
        current_step: Current step index (1-4).
    """
    steps = [
        "🧬 Data Prep",
        "🚀 Aligning",
        "📊 Statistics",
        "📓 Lab Notebook"
    ]
    
    # Custom CSS for the stepper
    st.markdown("""
        <style>
        .stepper-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding: 1rem;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .step-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            position: relative;
        }
        .step-bubble {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.8rem;
            margin-bottom: 0.5rem;
            background: #181b21;
            border: 2px solid #333;
            color: #666;
            z-index: 1;
        }
        .step-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
        }
        .step-item.active .step-bubble {
            background: var(--primary-color);
            border-color: var(--primary-color);
            color: white;
            box-shadow: 0 0 15px rgba(255, 126, 66, 0.4);
        }
        .step-item.active .step-label {
            color: var(--primary-color);
            font-weight: bold;
        }
        .step-item.complete .step-bubble {
            background: #4caf50;
            border-color: #4caf50;
            color: white;
        }
        .step-item.complete .step-label {
            color: #4caf50;
        }
        .step-line {
            position: absolute;
            top: 15px;
            left: 50%;
            width: 100%;
            height: 2px;
            background: #333;
            z-index: 0;
        }
        .step-item:last-child .step-line {
            display: none;
        }
        .step-item.complete .step-line {
            background: #4caf50;
        }
        </style>
    """, unsafe_allow_html=True)
    
    stepper_html = '<div class="stepper-container fade-in">'
    for i, label in enumerate(steps):
        idx = i + 1
        status_class = ""
        bubble_content = str(idx)
        
        if idx < current_step:
            status_class = "complete"
            bubble_content = "✓"
        elif idx == current_step:
            status_class = "active"
        
        stepper_html += f"""
            <div class="step-item {status_class}">
                <div class="step-bubble">{bubble_content}</div>
                <div class="step-label">{label}</div>
                <div class="step-line"></div>
            </div>
        """
    stepper_html += '</div>'
    
    st.markdown(stepper_html, unsafe_allow_html=True)
