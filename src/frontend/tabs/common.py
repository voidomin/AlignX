import streamlit as st
import yaml
from pathlib import Path
from typing import Dict, Any

@st.cache_data
def load_guided_data() -> Dict[str, Any]:
    """Load learning and help content from YAML file."""
    path = Path(__file__).parent.parent.parent / "resources" / "guided_data.yaml"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {"learning_cards": {}, "help_expanders": {}}

def render_learning_card(tab_name: str) -> None:
    """
    Render a context-aware learning card for Guided Mode.
    
    Args:
        tab_name: The name of the current tab (e.g., 'Summary', 'Sequence').
    """
    if not st.session_state.get('guided_mode', False):
        return

    data = load_guided_data()
    content = data.get("learning_cards", {})

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
    data = load_guided_data()
    helps = data.get("help_expanders", {})
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
    
    stepper_html = '<div class="stepper-container fade-in">\n'
    for i, label in enumerate(steps):
        idx = i + 1
        status_class = "complete" if idx < current_step else "active" if idx == current_step else ""
        bubble_content = "✓" if idx < current_step else str(idx)
        
        stepper_html += f'<div class="step-item {status_class}">\n'
        stepper_html += f'<div class="step-bubble">{bubble_content}</div>\n'
        stepper_html += f'<div class="step-label">{label}</div>\n'
        stepper_html += '<div class="step-line"></div>\n'
        stepper_html += '</div>\n'
        
    stepper_html += '</div>'
    
    st.markdown(stepper_html, unsafe_allow_html=True)
