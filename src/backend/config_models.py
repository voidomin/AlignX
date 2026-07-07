"""
Configuration models for the Mustang pipeline using Pydantic V2.
"""

import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

logger = logging.getLogger(__name__)


class CacheConfig(BaseModel):
    max_cache_size_mb: int = Field(1000, description="Maximum size of PDB cache in MB")
    enabled: bool = Field(True, description="Whether persistent caching is enabled")


class AppConfig(BaseModel):
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")


class CoreConfig(BaseModel):
    max_proteins: int = Field(20, ge=2, le=100)


class PDBConfig(BaseModel):
    source_url: str = Field("https://files.rcsb.org/download/")
    timeout: int = Field(60, ge=1)
    max_file_size_mb: int = Field(500, ge=1)
    retry_attempts: int = Field(3, ge=0)


class FilteringConfig(BaseModel):
    auto_filter_large_files: bool = True
    size_threshold_mb: int = Field(50, ge=1)
    default_chain: Optional[str] = None
    remove_heteroatoms: bool = True
    remove_water: bool = True
    remove_ligands: bool = False


class MustangConfig(BaseModel):
    backend: str = Field("auto")
    executable_path: Optional[str] = None  # None = auto-detect at runtime
    timeout: int = Field(600, ge=1)

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        if v.lower() not in ("auto", "native", "wsl"):
            raise ValueError("backend must be 'auto', 'native', or 'wsl'")
        return v.lower()


class PhylipConfig(BaseModel):
    executable: str = "neighbor"
    method: str = "neighbor_joining"
    bootstrap: int = Field(100, ge=1)


class PyMolConfig(BaseModel):
    enabled: bool = True
    executable: str = "pymol"
    headless: bool = True
    ray_trace: bool = False
    image_width: int = Field(1920, ge=640)
    image_height: int = Field(1080, ge=480)


class OutputConfig(BaseModel):
    base_dir: str = "results"
    keep_intermediates: bool = True
    formats: List[str] = Field(default_factory=lambda: ["html"])


class VisualizationConfig(BaseModel):
    heatmap_colormap: str = "RdYlBu_r"
    tree_format: str = "rectangular"
    dpi: int = Field(300, ge=72)


class PerformanceConfig(BaseModel):
    max_workers: int = Field(4, ge=1, le=32)
    chunk_size: int = Field(8192, ge=1024)


class DebugConfig(BaseModel):
    verbose_logging: bool = False
    save_raw_outputs: bool = False


class FoldseekLocalConfig(BaseModel):
    """Settings for the self-hosted Foldseek backend (see FoldseekRunner) -
    a local binary + search database as an alternative to the public API's
    shared rate limit. Provisioning a real database is a deployment-time
    step; these fields just point at wherever that ends up living."""

    binary_path: Optional[str] = None
    database_dir: Optional[str] = None
    timeout: int = Field(300, ge=1)


class FoldseekConfig(BaseModel):
    backend: str = Field("api")
    base_url: str = Field("https://search.foldseek.com")
    timeout: int = Field(30, ge=1)
    poll_interval_seconds: int = Field(10, ge=1)
    max_poll_attempts: int = Field(60, ge=1)
    default_databases: List[str] = Field(default_factory=lambda: ["pdb100", "afdb50"])
    local: FoldseekLocalConfig = Field(default_factory=FoldseekLocalConfig)

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        if v.lower() not in ("api", "local"):
            raise ValueError("backend must be 'api' or 'local'")
        return v.lower()


class AnnotationConfig(BaseModel):
    timeout: int = Field(15, ge=1)
    top_n_neighbors: int = Field(10, ge=1)
    # InterPro/QuickGO/SIFTS/STRING/Reactome data changes rarely, so a
    # multi-week cache is reasonable - see AnnotationAggregator's
    # persistent cache (HistoryDatabase.get/set_annotation_cache).
    cache_ttl_days: int = Field(30, ge=1)
    # Minimum Foldseek match probability (0-1) a neighbor's OWN structural
    # hit needs to count toward a Public/Student function hypothesis -
    # having curated annotations isn't enough on its own if the structural
    # match was weak. See AnnotationAggregator.high_confidence_annotated_count.
    min_confident_probability: float = Field(0.5, ge=0.0, le=1.0)


# Sections only the FastAPI/Discover side ever reads - config.yaml is
# validated by the SAME PipelineConfig for every caller, Streamlit's
# app.py/pages/ included (see src/utils/config_loader.py), even though
# Streamlit never touches any of these. A schema problem here must not
# take down the whole config load for an interface that doesn't even use
# it - see PipelineConfig._soften_optional_sections below. This already
# almost happened for real: the commit that tightened FoldseekConfig/
# AnnotationConfig's validation would have done exactly this for anyone
# with a malformed foldseek:/annotation: block.
_SOFT_VALIDATED_SECTIONS: Dict[str, type] = {
    "cache": CacheConfig,
    "foldseek": FoldseekConfig,
    "annotation": AnnotationConfig,
}


class PipelineConfig(BaseModel):
    """Root configuration model."""

    app: AppConfig
    core: CoreConfig
    pdb: PDBConfig
    filtering: FilteringConfig
    mustang: MustangConfig
    phylip: PhylipConfig
    pymol: PyMolConfig
    output: OutputConfig
    visualization: VisualizationConfig
    performance: PerformanceConfig
    debug: DebugConfig
    cache: Optional[CacheConfig] = Field(default_factory=CacheConfig)
    foldseek: Optional[FoldseekConfig] = Field(default_factory=FoldseekConfig)
    annotation: Optional[AnnotationConfig] = Field(default_factory=AnnotationConfig)

    @model_validator(mode="before")
    @classmethod
    def _soften_optional_sections(cls, data: Any) -> Any:
        """A bad value in an optional, Discover-only section (foldseek/
        annotation/cache) must not fail validation of the entire config -
        every other section is required precisely because both Compare and
        Discover (and Streamlit) genuinely depend on them, but these three
        are used by Discover/perf-tuning only. Falls back to that section's
        own defaults with a logged warning instead of raising, so a mistake
        here can never SystemExit(1) an interface that doesn't even read it."""
        if not isinstance(data, dict):
            return data
        for key, model_cls in _SOFT_VALIDATED_SECTIONS.items():
            section = data.get(key)
            if section is not None:
                try:
                    model_cls(**section)
                except ValidationError as e:
                    logger.warning(
                        f"Ignoring invalid '{key}' config section (falling back "
                        f"to defaults) - this only affects Discover mode, not "
                        f"Compare or the Streamlit app: {e}"
                    )
                    # Pydantic v2's default_factory only kicks in for a MISSING
                    # key - explicitly passing None would just set the field to
                    # None instead, so the key must be removed entirely.
                    del data[key]
        return data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to raw dictionary for backward compatibility."""
        return self.model_dump()
