import pytest
from src.utils.config_loader import load_config
import yaml


def test_valid_config_loading():
    """Test that a valid config.yaml loads correctly."""
    config = load_config("config.yaml")
    assert isinstance(config, dict)
    assert config["app"]["name"] == "Mustang Structural Alignment Pipeline"
    assert "core" in config
    assert "pdb" in config


def test_invalid_config_type(tmp_path):
    """Test that invalid types raise SystemExit via Pydantic."""
    invalid_config = {
        "app": {"name": "Test", "version": "1.0.0"},
        "core": {"max_proteins": "not_an_int"},  # Should be int
        "pdb": {},
        "filtering": {},
        "mustang": {},
        "phylip": {},
        "pymol": {},
        "output": {},
        "visualization": {},
        "performance": {},
        "debug": {},
    }

    config_file = tmp_path / "invalid_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(invalid_config, f)

    with pytest.raises(SystemExit):
        load_config(str(config_file))


def test_missing_required_field(tmp_path):
    """Test that missing required fields raise SystemExit."""
    incomplete_config = {
        "app": {"name": "Test"},  # Missing version
        "core": {},
        "pdb": {},
        "filtering": {},
        "mustang": {},
        "phylip": {},
        "pymol": {},
        "output": {},
        "visualization": {},
        "performance": {},
        "debug": {},
    }

    config_file = tmp_path / "incomplete_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(incomplete_config, f)

    with pytest.raises(SystemExit):
        load_config(str(config_file))


if __name__ == "__main__":
    # Rapid manual verification
    try:
        print("Verifying current config.yaml...")
        config = load_config("config.yaml")
        print("✅ Current config.yaml is valid.")
    except Exception as e:
        print(f"❌ Current config.yaml is invalid: {e}")
