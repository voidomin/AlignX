"""
Configuration models for the Mustang pipeline using Pydantic V2.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


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
    executable_path: str = "mustang"
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to raw dictionary for backward compatibility."""
        return self.model_dump()
