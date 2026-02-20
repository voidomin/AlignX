"""Configuration loader for the Mustang pipeline."""

import yaml
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file and environment variables.
    
    Args:
        config_path: Path to the configuration YAML file
        
    Returns:
        Dictionary containing all configuration settings
    """
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Load YAML configuration
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables if present
    _override_from_env(config)
    
    # Create necessary directories
    _create_directories(config)
    
    return config


def save_config(config: Dict[str, Any], config_path: str = "config.yaml") -> None:
    """
    Save configuration dictionary back to the YAML file.
    
    Args:
        config: Configuration dictionary to save
        config_path: Path to the configuration YAML file
    """
    config_file = Path(config_path)
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _override_from_env(config: Dict[str, Any]) -> None:
    """Override config values with environment variables."""
    env_mappings = {
        'MUSTANG_BACKEND': ['mustang', 'backend'],
        'MUSTANG_PATH': ['mustang', 'executable_path'],
        'PHYLIP_PATH': ['phylip', 'executable'],
        'PYMOL_PATH': ['pymol', 'executable'],
        'WORK_DIR': ['output', 'work_dir'],
        'RESULTS_DIR': ['output', 'base_dir'],
        'LOG_LEVEL': ['debug', 'log_level'],
    }
    
    for env_var, config_path in env_mappings.items():
        value = os.getenv(env_var)
        if value:
            _set_nested_value(config, config_path, value)


def _set_nested_value(config: Dict[str, Any], path: list, value: Any) -> None:
    """Set a value in a nested dictionary using a path list."""
    current = config
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _create_directories(config: Dict[str, Any]) -> None:
    """Create necessary directories for pipeline operation."""
    directories = [
        config.get('output', {}).get('base_dir', 'results'),
        'temp',
        'logs',
        'data/raw',
        'data/cleaned',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def get_config_value(config: Dict[str, Any], *keys, default=None) -> Any:
    """
    Safely get a nested configuration value.
    
    Args:
        config: Configuration dictionary
        *keys: Sequence of keys to navigate the nested dict
        default: Default value if key not found
        
    Returns:
        Configuration value or default
        
    Example:
        >>> get_config_value(config, 'mustang', 'backend', default='auto')
    """
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
