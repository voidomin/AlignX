import subprocess
import sys


def test_lazy_loading_in_clean_process():
    """
    Spawns a clean Python process, imports core backend modules,
    and verifies that heavy visualization/bioinformatics packages
    are NOT imported eagerly (retaining low memory baseline).
    """
    code = """
import sys
# Import core backend modules
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer

# Heavy packages that should be lazy loaded
heavy_packages = ['matplotlib', 'seaborn', 'plotly', 'Bio']
loaded = [pkg for pkg in heavy_packages if pkg in sys.modules]
if loaded:
    print(f"FAILED: {loaded} was imported eagerly")
    sys.exit(1)
print("SUCCESS")
sys.exit(0)
"""
    import os
    from pathlib import Path

    project_root = str(Path(__file__).parent.parent.resolve())

    # Inherit existing environment variables to ensure WinSock/asyncio can load on Windows
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=project_root,
        env=env,
    )
    assert result.returncode == 0, (
        f"Lazy loading check failed: {result.stdout.strip()} | "
        f"Stderr: {result.stderr.strip()}"
    )
