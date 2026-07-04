"""
Foldseek Runner Module.
Wraps a locally-installed Foldseek binary as an alternative to
FoldseekClient's public-API backend (see docs/ROADMAP_V3.md's Phase 5 note
on the public API's shared 0.1 qps rate limit becoming a real ceiling at
scale). Mirrors MustangRunner's native/WSL detection pattern.

Scope note: this makes local execution *possible* and *proven* against a
small hand-built test database (see tests + the live verification recorded
in docs/ROADMAP_V3.md) - it does not ship a production-scale search
database. Downloading/building real PDB100- or AFDB-scale databases (many
GB to 100+ GB) is a deployment-time operational decision, not something
this module does, the same way installing WSL/Mustang itself is left to
the user rather than automated.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger()

WSL_EXE = "C:/Windows/System32/wsl.exe"

# Columns chosen to map directly onto the same hit-dict shape
# FoldseekClient.parse_hits() produces from the public API's JSON response,
# so downstream code (AnnotationAggregator, DiscoveryCoordinator) doesn't
# need to know or care which backend actually ran the search. taxid/taxname
# are deliberately excluded: they require the target database to have
# taxonomy annotation (`foldseek createtaxdb`), which an ad-hoc directory of
# structure files doesn't have - a real production database build would add
# this, and the taxId field would come through the same way it does from
# the public API's AFDB/pdb100 databases.
_FORMAT_COLUMNS = [
    "query",
    "target",
    "evalue",
    "prob",
    "fident",
    "alnlen",
    "qstart",
    "qend",
    "tstart",
    "tend",
]


class FoldseekRunner:
    """Wrapper for running Foldseek structural search against a local
    directory of structure files (or a pre-built Foldseek database)."""

    # Cached across all instances for this process's lifetime, same
    # rationale as MustangRunner._cached_installation: the WSL check is a
    # slow subprocess call and installation status can't change mid-run.
    _cached_installation = None

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        local_cfg = config.get("foldseek", {}).get("local", {})
        self.binary_path = local_cfg.get("binary_path")
        self.timeout = local_cfg.get("timeout", 300)

        self.is_linux = sys.platform.startswith("linux")
        self.is_windows = sys.platform.startswith("win")
        self.use_wsl = False
        self.executable: Optional[str] = None

    def check_installation(self) -> Tuple[bool, str]:
        if FoldseekRunner._cached_installation is not None:
            success, msg, use_wsl, executable = FoldseekRunner._cached_installation
            self.use_wsl, self.executable = use_wsl, executable
            return success, msg

        success, msg = self._perform_installation_check()
        FoldseekRunner._cached_installation = (
            success,
            msg,
            self.use_wsl,
            self.executable,
        )
        return success, msg

    def _perform_installation_check(self) -> Tuple[bool, str]:
        if self.binary_path:
            if self.is_windows:
                return self._verify_wsl_binary(Path(self.binary_path))
            return self._verify_native_binary(self.binary_path)

        # No explicit path configured: try native PATH lookup first (the
        # expected case in Docker/Linux production), then fall back to a
        # WSL PATH lookup on Windows dev machines.
        native = shutil.which("foldseek")
        if native:
            return self._verify_native_binary(native)

        if self.is_windows:
            wsl_path = shutil.which("wsl") or WSL_EXE
            try:
                res = subprocess.run(
                    [wsl_path, "which", "foldseek"],
                    capture_output=True,
                    timeout=10,
                    text=True,
                )
                if res.returncode == 0 and res.stdout.strip():
                    self.use_wsl = True
                    self.executable = res.stdout.strip()
                    return True, f"Found Foldseek in WSL at {self.executable}"
            except Exception as e:
                logger.debug(f"WSL foldseek lookup failed: {e}")

        return False, "Foldseek binary not found (set foldseek.local.binary_path)"

    def _verify_native_binary(self, path_str: str) -> Tuple[bool, str]:
        """Takes a plain string, not a Path, since wrapping a POSIX-style
        native path in pathlib.Path and back to str() on a Windows dev
        machine (running the WSL backend for local testing) would silently
        rewrite its separators to backslashes."""
        try:
            subprocess.run([path_str], capture_output=True, timeout=5)
            self.use_wsl = False
            self.executable = path_str
            return True, f"Native Foldseek verified at {path_str}"
        except Exception as e:
            return False, f"Native Foldseek binary check failed: {e}"

    def _verify_wsl_binary(self, path: Path) -> Tuple[bool, str]:
        wsl_str = self._convert_to_wsl_path(path)
        wsl_path = shutil.which("wsl") or WSL_EXE
        try:
            res = subprocess.run(
                [wsl_path, wsl_str], capture_output=True, timeout=5
            )
            if res.returncode != 127:
                self.use_wsl = True
                self.executable = wsl_str
                return True, f"WSL Foldseek verified at {wsl_str}"
        except Exception as e:
            logger.debug(f"WSL foldseek binary check failed: {e}")
        return False, f"WSL Foldseek binary not found at {wsl_str}"

    def _convert_to_wsl_path(self, windows_path: Path) -> str:
        path_str = str(windows_path.absolute()).replace("\\", "/")
        if len(path_str) >= 2 and path_str[1] == ":":
            path_str = f"/mnt/{path_str[0].lower()}{path_str[2:]}"
        return path_str

    def search_against_directory(
        self, query_path: Path, target_dir: Path, tmp_dir: Path
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Runs `foldseek easy-search` with the query file against every
        structure in target_dir (or a pre-built Foldseek database at that
        path), returning hits in the same shape FoldseekClient.parse_hits()
        produces from the public API.
        """
        success, msg = self.check_installation()
        if not success:
            return False, msg, []

        tmp_dir.mkdir(parents=True, exist_ok=True)
        result_path = tmp_dir / "result.tsv"

        if self.use_wsl:
            wsl_path = shutil.which("wsl") or WSL_EXE
            cmd = [
                wsl_path,
                self.executable,
                "easy-search",
                self._convert_to_wsl_path(query_path),
                self._convert_to_wsl_path(target_dir),
                self._convert_to_wsl_path(result_path),
                self._convert_to_wsl_path(tmp_dir / "foldseek_tmp"),
                "--format-output",
                ",".join(_FORMAT_COLUMNS),
                "-v",
                "1",
            ]
        else:
            cmd = [
                self.executable,
                "easy-search",
                str(query_path),
                str(target_dir),
                str(result_path),
                str(tmp_dir / "foldseek_tmp"),
                "--format-output",
                ",".join(_FORMAT_COLUMNS),
                "-v",
                "1",
            ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=self.timeout, text=True
            )
            if result.returncode != 0:
                return False, f"Foldseek search failed: {result.stderr[-500:]}", []
        except subprocess.TimeoutExpired:
            return False, f"Foldseek search timed out after {self.timeout}s", []
        except Exception as e:
            return False, f"Foldseek search failed: {e}", []

        if not result_path.exists():
            return False, "Foldseek produced no result file", []

        hits = self._parse_tsv(result_path)
        return True, "Local Foldseek search completed successfully", hits

    @staticmethod
    def _parse_tsv(result_path: Path) -> List[Dict[str, Any]]:
        hits = []
        for line in result_path.read_text().splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            if len(fields) != len(_FORMAT_COLUMNS):
                continue
            row = dict(zip(_FORMAT_COLUMNS, fields))
            try:
                hits.append(
                    {
                        "query": row["query"],
                        "target": row["target"],
                        "eval": float(row["evalue"]),
                        "prob": float(row["prob"]),
                        "seqId": round(float(row["fident"]) * 100, 1),
                        "alnLength": int(row["alnlen"]),
                        "qStartPos": int(row["qstart"]),
                        "qEndPos": int(row["qend"]),
                        "dbStartPos": int(row["tstart"]),
                        "dbEndPos": int(row["tend"]),
                    }
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping malformed Foldseek result row: {e}")
        return hits
