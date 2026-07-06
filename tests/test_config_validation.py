import pytest
from src.utils.config_loader import load_config
import yaml


def test_valid_config_loading():
    """Test that a valid config.yaml loads correctly."""
    config = load_config("config.yaml")
    assert isinstance(config, dict)
    assert config["app"]["name"] == "StructScope"
    assert "core" in config
    assert "pdb" in config


def test_foldseek_and_annotation_sections_survive_validation(tmp_path):
    """Regression test: PipelineConfig didn't define `foldseek`/`annotation`
    fields, so Pydantic's default extra-field handling silently dropped
    both sections from every loaded config - every "config-driven" Foldseek/
    annotation setting was actually just falling back to hardcoded Python
    defaults the whole time, undetected because those defaults happened to
    match what config.yaml specified. Found while live-testing the local
    Foldseek backend (foldseek.backend: local was silently ignored)."""
    config = load_config("config.yaml")
    assert "foldseek" in config
    assert "backend" in config["foldseek"]
    assert "default_databases" in config["foldseek"]
    assert "local" in config["foldseek"]
    assert "binary_path" in config["foldseek"]["local"]
    assert "database_dir" in config["foldseek"]["local"]
    assert "annotation" in config
    assert "top_n_neighbors" in config["annotation"]


def test_foldseek_local_config_round_trips_custom_values(tmp_path):
    minimal_config = {
        "app": {"name": "Test", "version": "1.0.0"},
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
        "foldseek": {
            "backend": "local",
            "local": {"binary_path": "/usr/bin/foldseek", "database_dir": "/data/db"},
        },
    }
    config_file = tmp_path / "custom_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(minimal_config, f)

    config = load_config(str(config_file))

    assert config["foldseek"]["backend"] == "local"
    assert config["foldseek"]["local"]["binary_path"] == "/usr/bin/foldseek"
    assert config["foldseek"]["local"]["database_dir"] == "/data/db"


def test_foldseek_invalid_backend_falls_back_to_defaults_instead_of_crashing(
    tmp_path, caplog
):
    """A bad foldseek: value must not SystemExit the whole config load -
    load_config() is shared by Streamlit's app.py/pages/, which never reads
    foldseek: at all, so a Discover-only config mistake crashing Streamlit
    too would be exactly the bug this regression test guards against (see
    PipelineConfig._soften_optional_sections)."""
    invalid_config = {
        "app": {"name": "Test", "version": "1.0.0"},
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
        "foldseek": {"backend": "not-a-real-backend"},
    }
    config_file = tmp_path / "bad_backend_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(invalid_config, f)

    config = load_config(str(config_file))

    assert config["foldseek"]["backend"] == "api"  # fell back to the default
    assert any(
        "foldseek" in r.message and "not-a-real-backend" in r.message
        for r in caplog.records
    )


def test_annotation_and_cache_sections_also_fall_back_gracefully(tmp_path, caplog):
    """Same soft-fallback treatment applies to annotation: and cache: -
    both are Discover/perf-only, never read by Streamlit or Compare mode."""
    invalid_config = {
        "app": {"name": "Test", "version": "1.0.0"},
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
        "annotation": {"min_confident_probability": 5.0},  # out of the 0-1 range
        "cache": {"max_cache_size_mb": "not-a-number"},
    }
    config_file = tmp_path / "bad_annotation_cache_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(invalid_config, f)

    config = load_config(str(config_file))

    assert config["annotation"]["min_confident_probability"] == 0.5  # default
    assert config["cache"]["max_cache_size_mb"] == 1000  # default
    warned_sections = {
        "annotation" if "annotation" in r.message else "cache" if "cache" in r.message else None
        for r in caplog.records
    }
    assert {"annotation", "cache"} <= warned_sections


def test_core_section_still_hard_fails_on_invalid_values(tmp_path):
    """Sections every interface genuinely depends on (mustang, pdb, etc.)
    must keep hard-failing - only the Discover-only optional sections get
    the soft fallback above."""
    invalid_config = {
        "app": {"name": "Test", "version": "1.0.0"},
        "core": {},
        "pdb": {},
        "filtering": {},
        "mustang": {"backend": "not-a-real-backend"},
        "phylip": {},
        "pymol": {},
        "output": {},
        "visualization": {},
        "performance": {},
        "debug": {},
    }
    config_file = tmp_path / "bad_mustang_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(invalid_config, f)

    with pytest.raises(SystemExit):
        load_config(str(config_file))


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
