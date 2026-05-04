import subprocess
import shutil
import sys
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from src.utils.logger import get_logger

logger = get_logger()

# Constants for literals
MUSTANG_TARBALL = "mustang.tgz"
MUSTANG_BUILD_DIR = "mustang_build"
WSL_EXE = "C:/Windows/System32/wsl.exe"
ALIGN_FASTA = "alignment.fasta"
ALIGN_PDB = "alignment.pdb"
ALIGN_AFASTA = "alignment.afasta"
MUSTANG_URL = "http://lcb.infotech.monash.edu.au/mustang/mustang_v3.2.3.tgz"


class MustangRunner:
    """Wrapper for running Mustang structural alignment."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Mustang Runner."""
        self.config = config
        self.backend = config.get("mustang", {}).get("backend", "auto")
        self.executable = config.get("mustang", {}).get("executable_path", None)
        self.timeout = config.get("mustang", {}).get("timeout", 600)

        # Platform detection
        self.is_linux = sys.platform.startswith("linux")
        self.is_windows = sys.platform.startswith("win")
        self.use_wsl = False

        logger.info(
            f"Initialized Mustang Runner (Platform: {sys.platform}, Mode: {self.backend})"
        )

    @property
    def base_dir(self):
        """Lazy load base_dir to handle stale session state."""
        if not hasattr(self, "_base_dir"):
            self._base_dir = Path(__file__).resolve().parent.parent.parent
        return self._base_dir

    def _download_mustang_source(self, dest_path: Path) -> bool:
        """Download Mustang source tarball with SSL bypass for restricted environments."""
        import urllib.request
        import ssl

        try:
            # Create unverified context to bypass SSL issues on Streamlit Cloud
            # Note: This is a known workaround for specific server certificate issues.
            context = ssl._create_unverified_context()
            logger.info(f"Downloading from {MUSTANG_URL} (SSL verification disabled)...")

            with urllib.request.urlopen(MUSTANG_URL, context=context, timeout=60) as response, \
                 open(dest_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)

            logger.info(f"Successfully downloaded {MUSTANG_TARBALL}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {MUSTANG_TARBALL}: {e}")
            return False

    def _prepare_compilation_dir(self, build_dir: Path, bundled_tarball: Path) -> Optional[Path]:
        """Clear and prepare the build directory for compilation."""
        if build_dir.exists():
            try:
                shutil.rmtree(build_dir)
            except Exception as e:
                logger.warning(f"Could not clear build directory: {e}. Attempting to proceed...")

        build_dir.mkdir(exist_ok=True)
        shutil.copy(bundled_tarball, build_dir / MUSTANG_TARBALL)
        shutil.unpack_archive(build_dir / MUSTANG_TARBALL, build_dir)

        extracted_dirs = [d for d in build_dir.iterdir() if d.is_dir()]
        return extracted_dirs[0] if extracted_dirs else None

    def _execute_compilation(self, src_dir: Path) -> bool:
        """Execute the 'make' command natively or via WSL."""
        use_wsl_for_make = self.is_windows and shutil.which("wsl")
        cmd = ["wsl", "make"] if use_wsl_for_make else ["make"]

        logger.info(f"Compiling with {'WSL' if use_wsl_for_make else 'native'} make...")
        try:
            subprocess.run(cmd, cwd=str(src_dir.absolute()), check=True, timeout=300)
            return True
        except Exception as e:
            logger.error(f"Compilation command failed: {e}")
            return False

    def _locate_compiled_binary(self, src_dir: Path) -> bool:
        """Locate the compiled binary and set runner state."""
        bin_dir = src_dir / "bin"
        if not bin_dir.exists():
            return False

        binaries = list(bin_dir.glob("mustang*"))
        if not binaries:
            return False

        binary = binaries[0]
        if self.is_windows:
            self.wsl_binary = binary
        else:
            self.executable = str(binary.absolute())
            # Ensure binary is executable on Linux
            # Standard permission for executable binaries
            os.chmod(self.executable, 0o755)
        return True

    def _compile_from_source(self) -> bool:
        """Orchestrate the compilation of Mustang from source."""
        try:
            logger.info("Attempting to compile Mustang from bundled source...")
            bundled_tarball = self.base_dir / MUSTANG_TARBALL

            if not bundled_tarball.exists() and not self._download_mustang_source(bundled_tarball):
                return False

            build_dir = self.base_dir / MUSTANG_BUILD_DIR
            src_dir = self._prepare_compilation_dir(build_dir, bundled_tarball)
            if not src_dir:
                logger.error("Extraction failed: No source directory found")
                return False

            if not self._execute_compilation(src_dir):
                return False

            if self._locate_compiled_binary(src_dir):
                return True

            logger.error("Compilation finished but binary not found")
            return False
        except Exception as e:
            logger.error(f"Compilation process error: {e}")
            return False

    def _check_native_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is available as a native binary."""
        path_check = self.mustang_path if hasattr(self, "mustang_path") and self.mustang_path else None
        if path_check and path_check.exists():
            try:
                subprocess.run([str(path_check), "--help"], capture_output=True, timeout=2)
                self.use_wsl = False
                return True, f"Mustang binary found (Native {sys.platform})"
            except Exception as e:
                logger.debug(f"Native check failed at {path_check}: {e}")
        return False, ""

    def _check_wsl_system_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is installed within the WSL environment."""
        if not self.is_windows:
            return False, ""

        wsl_path = shutil.which("wsl") or WSL_EXE
        try:
            res = subprocess.run([wsl_path, "which", "mustang"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                self.use_wsl = True
                self.mustang_path = Path("mustang")
                self.executable = "mustang"
                logger.info(f"System Mustang found in WSL using {wsl_path}")
                return True, "System Mustang binary found (WSL)"
        except Exception as e:
            logger.debug(f"WSL check at {wsl_path} failed: {e}")
        return False, ""

    def _check_compiled_binary(self) -> Tuple[bool, str]:
        """Search for a previously compiled binary in the build directory."""
        build_dir = self.base_dir / MUSTANG_BUILD_DIR
        if not build_dir.exists():
            return False, ""

        binaries = list(build_dir.glob("**/bin/mustang*"))
        if not binaries:
            return False, ""

        bin_path = binaries[0]
        if self.is_windows:
            return self._verify_wsl_binary(bin_path)

        return self._verify_native_linux_binary(bin_path)

    def _verify_wsl_binary(self, bin_path: Path) -> Tuple[bool, str]:
        """Verify if a Linux binary can be run via WSL."""
        try:
            wsl_str = self._convert_to_wsl_path(bin_path)
            res = subprocess.run(["wsl", wsl_str, "--help"], capture_output=True, timeout=5)
            if res.returncode != 127:
                self.use_wsl = True
                self.mustang_path = bin_path
                return True, "Compiled Mustang found (WSL)"
        except Exception as e:
            logger.debug(f"WSL compiled binary check failed: {e}")
        return False, ""

    def _verify_native_linux_binary(self, bin_path: Path) -> Tuple[bool, str]:
        """Verify if a binary can be run natively on Linux."""
        try:
            # Set execute permissions
            os.chmod(bin_path, 0o755)
            subprocess.run([str(bin_path), "--help"], capture_output=True, timeout=2)
            self.use_wsl = False
            self.mustang_path = bin_path
            self.executable = str(bin_path.absolute())
            return True, "Compiled Mustang found (Native Linux)"
        except Exception as e:
            logger.debug(f"Native compiled binary check failed: {e}")
        return False, ""

    def _check_mustang(self) -> Tuple[bool, str]:
        """Aggregated check for Mustang availability."""
        success, msg = self._check_native_installation()
        if success: return success, msg

        success, msg = self._check_wsl_system_installation()
        if success: return success, msg

        success, msg = self._check_compiled_binary()
        if success: return success, msg

        return False, "Mustang binary not found"

    def check_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is properly installed with multi-platform fallbacks."""
        # 1. PATH Check
        path_binary = shutil.which("mustang")
        if path_binary:
            self.backend, self.executable = "native", path_binary
            return True, f"Found native Mustang in PATH: {path_binary}"

        # 2. Windows WSL specific deep check
        if self.is_windows:
            success, msg = self._deep_wsl_check()
            if success: return True, msg

        # 3. Local/Compiled check
        found, msg = self._check_mustang()
        if found: return True, msg

        # 4. Compilation fallback
        if self._compile_from_source():
            found, msg = self._check_mustang()
            if found:
                self._update_executable_from_check()
                return True, f"Compiled Mustang binary ({'WSL' if self.use_wsl else 'Native'})"

        logger.error("Mustang binary found neither in PATH nor in WSL")
        return False, "Mustang binary found neither in PATH nor in WSL"

    def _deep_wsl_check(self) -> Tuple[bool, str]:
        """Perform a robust check for Mustang in WSL on Windows."""
        wsl_path = shutil.which("wsl") or WSL_EXE
        try:
            res = subprocess.run([wsl_path, "which", "mustang"], capture_output=True, timeout=30)
            stdout_str = res.stdout.decode("utf-8", errors="ignore").replace("\x00", "").strip()

            if res.returncode == 0 and "mustang" in stdout_str:
                self.use_wsl, self.mustang_path, self.executable = True, Path("mustang"), "mustang"
                if self.backend in ["auto", "bio3d"]: self.backend = "wsl"
                return True, f"System Mustang found in WSL: {stdout_str}"
        except Exception as e:
            logger.warning(f"WSL check exception: {e}")
        return False, ""

    def _update_executable_from_check(self):
        """Update executable path after successful compilation/check."""
        if self.use_wsl:
            self.backend = "wsl"
            self.executable = "mustang" if str(self.mustang_path) == "mustang" else self._convert_to_wsl_path(self.mustang_path)
        else:
            self.backend, self.executable = "native", str(self.mustang_path)
        logger.info(f"Mustang installation verified: {self.executable} ({self.backend})")

    def run_alignment(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """Run Mustang alignment on multiple PDB files."""
        if len(pdb_files) < 2:
            return False, "Need at least 2 structures for alignment", None

        output_dir.mkdir(parents=True, exist_ok=True)
        local_pdb_files = []
        for pdb_file in pdb_files:
            dest_path = output_dir / pdb_file.name
            if not dest_path.exists():
                shutil.copy2(pdb_file, dest_path)
            local_pdb_files.append(dest_path)

        return self._run_native_mustang(local_pdb_files, output_dir)

    def _construct_command(self, pdb_files: List[Path], output_dir: Path) -> Tuple[List[str], Path]:
        """Construct the command line arguments for Mustang."""
        run_cwd = output_dir.absolute()
        input_filenames = [p.name for p in pdb_files]

        if not self.executable:
            self._fallback_executable()

        logger.info(f"Constructing command. Executable: {self.executable}, WSL: {self.use_wsl}")

        if self.use_wsl:
            wsl_exe = shutil.which("wsl") or WSL_EXE
            cmd = [wsl_exe, str(self.executable)]
        else:
            cmd = [shutil.which(str(self.executable)) or str(self.executable)]

        cmd.extend(["-i"] + input_filenames + ["-o", "alignment", "-F", "fasta", "-r", "ON"])
        return cmd, run_cwd

    def _fallback_executable(self):
        """Set fallback executable if none specified."""
        wsl_path = shutil.which("wsl") or WSL_EXE
        if self.is_windows and (shutil.which("wsl") or Path(wsl_path).exists()):
            self.use_wsl, self.executable = True, "mustang"
        else:
            self.executable = "mustang"

    def _run_native_mustang(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """Run native Mustang binary with live telemetry."""
        try:
            cmd, run_cwd = self._construct_command(pdb_files, output_dir)
            timeout = 1800 if any("af-" in p.name.lower() for p in pdb_files) else self.timeout

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=str(run_cwd), bufsize=1, universal_newlines=True
            )

            stdout, stderr = self._stream_process_output(process, timeout)
            
            # Save logs
            (output_dir / "mustang.log").write_text(f"{stdout}\n=== STDERR ===\n{stderr}")

            return self._finalize_alignment_output(output_dir, process.returncode)

        except Exception as e:
            logger.error(f"Mustang execution error: {e}")
            return False, f"Mustang error: {e}", None

    def _stream_process_output(self, process, timeout) -> Tuple[str, str]:
        """Stream output from the process and handle timeout."""
        stdout_lines, start_time = [], time.time()
        
        while True:
            if time.time() - start_time > timeout:
                process.kill()
                raise TimeoutError(f"Mustang timed out after {timeout}s")

            line = process.stdout.readline()
            if not line and process.poll() is not None: break
            if line:
                logger.info(f"[Mustang] {line.strip()}")
                stdout_lines.append(line)

        return "".join(stdout_lines), process.stderr.read()

    def _finalize_alignment_output(self, output_dir: Path, return_code: int) -> Tuple[bool, str, Optional[Path]]:
        """Verify results and calculate RMSD matrix."""
        pdb_file = output_dir / ALIGN_PDB
        fasta_file = output_dir / ALIGN_FASTA

        if return_code != 0 and not pdb_file.exists():
            msg = f"Mustang failed (Exit {return_code})"
            if return_code == 139: msg += ". Possible structural divergence issue."
            return False, msg, None

        if not pdb_file.exists():
            return False, "Mustang did not produce alignment.pdb", None

        self._ensure_fasta_exists(output_dir, fasta_file)
        self._calculate_rmsd_post_alignment(pdb_file, fasta_file, output_dir)

        logger.info("Mustang alignment completed successfully")
        return True, "Alignment completed", output_dir

    def _ensure_fasta_exists(self, output_dir: Path, fasta_file: Path):
        """Standardize the FASTA output file location."""
        if fasta_file.exists(): return

        afasta = output_dir / ALIGN_AFASTA
        if afasta.exists():
            shutil.copy(afasta, fasta_file)
        else:
            possible = list(output_dir.glob("*.fasta"))
            if possible: shutil.copy(possible[0], fasta_file)

    def _calculate_rmsd_post_alignment(self, pdb_file: Path, fasta_file: Path, output_dir: Path):
        """Run the RMSD calculator on the alignment results."""
        try:
            from src.backend.rmsd_calculator import calculate_structure_rmsd
            logger.info("Computing RMSD matrix...")
            rmsd_df = calculate_structure_rmsd(pdb_file, fasta_file)
            if rmsd_df is not None:
                rmsd_df.to_csv(output_dir / "rmsd_matrix.csv")
        except Exception as e:
            logger.error(f"Failed to compute RMSD: {e}")

    def _convert_to_wsl_path(self, windows_path: Path) -> str:
        """Convert Windows path to WSL path format."""
        path_str = str(windows_path.absolute()).replace("\\", "/")
        if len(path_str) >= 2 and path_str[1] == ":":
            path_str = f"/mnt/{path_str[0].lower()}{path_str[2:]}"
        return path_str
