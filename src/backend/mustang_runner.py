import subprocess
import shutil
import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from src.utils.logger import get_logger

logger = get_logger()


class MustangRunner:
    """Wrapper for running Mustang structural alignment."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize Mustang Runner.

        Args:
            config: Configuration dictionary
        """
        self.config = config

        self.backend = config.get("mustang", {}).get("backend", "auto")
        self.executable = config.get("mustang", {}).get("executable_path", None)
        self.timeout = config.get("mustang", {}).get("timeout", 600)

        # Platform detection
        self.is_linux = sys.platform.startswith("linux")
        self.is_windows = sys.platform.startswith("win")
        self.use_wsl = False  # Default

        logger.info(
            f"Initialized Mustang Runner (Platform: {sys.platform}, Mode: {self.backend})"
        )

    def _compile_from_source(self) -> bool:
        """Attempt to compile Mustang from bundled source."""
        try:
            logger.info("Attempting to compile Mustang from bundled source...")

            # Check for bundled tarball
            bundled_tarball = Path("mustang.tgz")
            if not bundled_tarball.exists():
                logger.warning(
                    "Bundled mustang.tgz not found. Downloading from source..."
                )
                import urllib.request

                try:
                    url = "http://lcb.infotech.monash.edu.au/mustang/mustang_v3.2.3.tgz"
                    urllib.request.urlretrieve(url, "mustang.tgz")
                    logger.info("Successfully downloaded mustang.tgz")
                except Exception as e:
                    logger.error(f"Failed to download mustang.tgz: {e}")
                    return False

            build_dir = Path("mustang_build")
            if build_dir.exists():
                try:
                    shutil.rmtree(build_dir)
                except Exception as e:
                    logger.warning(
                        f"Could not clear existing build directory (might be in use): {e}. Attempting to proceed..."
                    )
            build_dir.mkdir(exist_ok=True)

            # Copy tarball to build dir
            shutil.copy(bundled_tarball, build_dir / "mustang.tgz")

            # Extract using shutil (more robust than tar command)
            shutil.unpack_archive(build_dir / "mustang.tgz", build_dir)

            # Find makefile directory (it unpacks into a subdir)
            # Handle potential variation in folder name
            extracted_dirs = [d for d in build_dir.iterdir() if d.is_dir()]
            if not extracted_dirs:
                logger.error("Extraction failed: No directory found")
                return False

            src_dir = extracted_dirs[0]
            logger.info(f"Source extracted to: {src_dir}")

            # Compile using make
            # Detect if we should use WSL for make (only on Windows if wsl exists)
            use_wsl_for_make = False
            if self.is_windows and shutil.which("wsl"):
                use_wsl_for_make = True

            if use_wsl_for_make:
                logger.info("Compiling with make inside WSL...")
                subprocess.run(
                    ["wsl", "make"],
                    cwd=str(src_dir.absolute()),
                    check=True,
                    timeout=300,
                )
            else:
                logger.info(f"Compiling with native make on {sys.platform}...")
                subprocess.run(
                    ["make"], cwd=str(src_dir.absolute()), check=True, timeout=300
                )

            # Locate binary
            bin_dir = src_dir / "bin"
            if bin_dir.exists():
                binaries = list(bin_dir.glob("mustang*"))
                if binaries:
                    # On Windows, we need WSL to run this Linux binary
                    if self.is_windows:
                        self.wsl_binary = binaries[0]
                    else:
                        # On Linux, we use it natively
                        self.executable = str(binaries[0].absolute())
                        os.chmod(self.executable, 0o755)  # Ensure executable
                    return True

            logger.error("Compilation finished but binary not found")
            return False

        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False

    def _check_mustang(self) -> Tuple[bool, str]:
        """Check if Mustang binary is available (Native, WSL, or Built)."""
        # 1. Check Native (Windows or Linux)
        if hasattr(self, "mustang_path") and self.mustang_path.exists():
            try:
                subprocess.run(
                    [str(self.mustang_path), "--help"], capture_output=True, timeout=2
                )
                self.use_wsl = False
                return True, f"Mustang binary found (Native {sys.platform})"
            except Exception as exc:
                logger.debug(f"Native mustang check failed: {exc}")

        # 2. Check System-wide WSL Binary (Only on Windows)
        if self.is_windows:
            wsl_path = shutil.which("wsl") or "C:/Windows/System32/wsl.exe"
            try:
                res = subprocess.run(
                    [wsl_path, "which", "mustang"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    self.use_wsl = True
                    self.mustang_path = Path("mustang")
                    self.executable = "mustang"
                    logger.info(f"System Mustang binary found in WSL using {wsl_path}")
                    return True, "System Mustang binary found (WSL)"
            except Exception as e:
                logger.debug(f"WSL check at {wsl_path} failed: {e}")

        # 3. Check Compiled Binary (Search build path)
        build_dir = self.base_dir / "mustang_build"
        if build_dir.exists():
            binaries = list(build_dir.glob("**/bin/mustang*"))
            if binaries:
                bin_path = binaries[0]
                if self.is_windows:
                    try:
                        wsl_str = self._convert_to_wsl_path(bin_path)
                        res = subprocess.run(
                            ["wsl", wsl_str, "--help"], capture_output=True, timeout=5
                        )
                        if res.returncode != 127:
                            self.use_wsl = True
                            self.mustang_path = bin_path
                            return True, "Compiled Mustang found (WSL)"
                    except Exception as exc:
                        logger.debug(f"WSL compiled binary check failed: {exc}")
                else:
                    # Linux Native
                    try:
                        os.chmod(bin_path, 0o755)
                        subprocess.run(
                            [str(bin_path), "--help"], capture_output=True, timeout=2
                        )
                        self.use_wsl = False
                        self.mustang_path = bin_path
                        return True, "Compiled Mustang found (Native Linux)"
                    except Exception as exc:
                        logger.debug(f"Native compiled binary check failed: {exc}")

        return False, "Mustang binary not found"

    @property
    def base_dir(self):
        """Lazy load base_dir to handle stale session state."""
        if not hasattr(self, "_base_dir"):
            self._base_dir = Path(__file__).resolve().parent.parent.parent
        return self._base_dir

    def check_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is properly installed with fallbacks."""

        # 1. Check if 'mustang' is in PATH (Native)
        path_binary = shutil.which("mustang")
        if path_binary:
            self.backend = "native"
            self.executable = path_binary  # Use absolute path found by shutil.which
            logger.info(f"Found native Mustang binary in PATH: {path_binary}")
            return True, f"Found native Mustang binary in PATH: {path_binary}"

        # 2. Check System-wide WSL Binary (Only on Windows)
        if self.is_windows:
            try:
                # Direct check for mustang in WSL
                # Note: WSL output might be UTF-16 in some terminals, leading to \x00 bytes
                # Increased timeout to 30s as WSL might need to spin up (cold start)
                wsl_path = shutil.which("wsl") or "C:/Windows/System32/wsl.exe"
                res = subprocess.run(
                    [wsl_path, "which", "mustang"], capture_output=True, timeout=30
                )

                # Robust decoding
                try:
                    stdout_str = res.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    stdout_str = res.stdout.decode("utf-16", errors="ignore")

                # Clean up null bytes if any remain
                stdout_str = stdout_str.replace("\x00", "").strip()

                if res.returncode == 0 and stdout_str and "mustang" in stdout_str:
                    self.use_wsl = True
                    self.mustang_path = Path("mustang")
                    self.executable = "mustang"
                    # Force backend to wsl if it was auto OR bio3d (prioritize native)
                    if self.backend in ["auto", "bio3d"]:
                        self.backend = "wsl"
                    logger.info(
                        f"System Mustang binary found in WSL ({wsl_path}): {stdout_str}"
                    )
                    return True, f"System Mustang binary found (WSL: {wsl_path})"
                else:
                    logger.warning(
                        f"WSL check failed using {wsl_path}. 'wsl which mustang' returned: '{stdout_str}' (Exit: {res.returncode})"
                    )
            except Exception as e:
                logger.warning(f"WSL check exception using {wsl_path}: {e}")

        # 3. Try to Compile
        if self._compile_from_source():
            # Re-check after compilation
            found, msg = self._check_mustang()
            if found:
                if getattr(self, "use_wsl", False):
                    self.backend = "wsl"
                    if str(self.mustang_path) == "mustang":
                        self.executable = "mustang"
                    else:
                        self.executable = self._convert_to_wsl_path(self.mustang_path)
                    return True, "Compiled Mustang binary (WSL)"
                else:
                    self.backend = "native"
                    self.executable = str(self.mustang_path)
                    return True, "Compiled Mustang binary (Native)"

        logger.error("Mustang binary found neither in PATH nor in WSL")
        return False, "Mustang binary found neither in PATH nor in WSL"

    def run_alignment(
        self, pdb_files: List[Path], output_dir: Path
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Run Mustang alignment on multiple PDB files.

        Args:
            pdb_files: List of PDB file paths
            output_dir: Output directory for results

        Returns:
            Tuple of (success, message, output_file_path)
        """
        if len(pdb_files) < 2:
            return False, "Need at least 2 structures for alignment", None

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy input files to output directory for self-contained results
        local_pdb_files = []
        for pdb_file in pdb_files:
            dest_path = output_dir / pdb_file.name
            if not dest_path.exists():
                shutil.copy2(pdb_file, dest_path)
            local_pdb_files.append(dest_path)

        # Native execution
        return self._run_native_mustang(local_pdb_files, output_dir)

    def _construct_command(
        self, pdb_files: List[Path], output_dir: Path
    ) -> Tuple[List[str], Path]:
        """
        Construct the command line arguments for Mustang.
        Returns: (command_list, run_cwd)
        """
        # We run in output_dir, so we can use filenames directly (files are copied there)
        run_cwd = output_dir.absolute()
        input_filenames = [p.name for p in pdb_files]

        output_prefix_arg = "alignment"

        if not self.executable:
            # Fallback: if check_installation was never called but wsl exists
            wsl_path = shutil.which("wsl") or "C:/Windows/System32/wsl.exe"
            if self.is_windows and (shutil.which("wsl") or Path(wsl_path).exists()):
                self.use_wsl = True
                self.executable = "mustang"
                logger.info(
                    f"No executable set, falling back to 'mustang' via WSL ({wsl_path})"
                )
            else:
                self.executable = "mustang"
                logger.info("No executable set, falling back to 'mustang' (Native)")

        logger.info(
            f"Constructing command. Executable: {self.executable}, WSL: {getattr(self, 'use_wsl', False)}"
        )

        if getattr(self, "use_wsl", False):
            wsl_exe = shutil.which("wsl") or "C:/Windows/System32/wsl.exe"
            cmd = [wsl_exe, str(self.executable)]
        else:
            # Native execution
            exe_str = str(self.executable)
            if os.path.isabs(exe_str) and Path(exe_str).exists():
                cmd = [exe_str]
            elif shutil.which(exe_str):
                cmd = [shutil.which(exe_str)]
            else:
                # If all else fails, just use the string and hope it's in path
                cmd = [exe_str]

        # Add arguments
        cmd.extend(
            ["-i"]
            + input_filenames
            + ["-o", output_prefix_arg, "-F", "fasta", "-r", "ON"]
        )

        return cmd, run_cwd

    def _run_native_mustang(
        self, pdb_files: List[Path], output_dir: Path
    ) -> Tuple[bool, str, Optional[Path]]:
        """Run native Mustang binary with live telemetry."""
        try:
            cmd, run_cwd = self._construct_command(pdb_files, output_dir)

            logger.info(f"EXACT MUSTANG COMMAND: {' '.join(cmd)}")
            logger.info(f"Running Mustang in CWD: {run_cwd}")

            # Complex diversity (e.g. 1BKV + Large AF) needs much more time
            # 30 minutes for complex suites, 10 minutes otherwise
            mustang_timeout = (
                1800
                if any("af-" in p.name.lower() for p in pdb_files)
                else self.timeout
            )

            # Use Popen to stream output line-by-line
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(run_cwd),
                bufsize=1,
                universal_newlines=True,
            )

            stdout_lines = []
            stderr_lines = []

            # Use a basic timer for timeout
            import time

            start_time = time.time()

            while True:
                # Check for timeout
                if time.time() - start_time > mustang_timeout:
                    process.kill()
                    logger.error(f"Mustang timed out after {mustang_timeout}s")
                    return (
                        False,
                        f"Alignment timed out after {mustang_timeout}s. Complex structural diversity may require more time or simpler comparisons.",
                        None,
                    )

                # Read line-by-line
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    clean_line = line.strip()
                    if clean_line:
                        logger.info(f"[Mustang] {clean_line}")
                        stdout_lines.append(line)

            # Capture remaining stderr
            stderr_out = process.stderr.read()
            if stderr_out:
                stderr_lines.append(stderr_out)
                for stderr_line in stderr_out.splitlines():
                    logger.warning(f"[Mustang-Err] {stderr_line}")

            return_code = process.returncode
            all_stdout = "".join(stdout_lines)
            all_stderr = "".join(stderr_lines)

            # Save output to log file
            log_file = output_dir / "mustang.log"
            with open(log_file, "w") as f:
                f.write(all_stdout)
                f.write("\n=== STDERR ===\n")
                f.write(all_stderr)

            # Check for output files
            afasta_file = output_dir / "alignment.afasta"
            fasta_file = output_dir / "alignment.fasta"
            pdb_file = output_dir / "alignment.pdb"

            is_definitely_failed = return_code != 0 and not pdb_file.exists()

            if is_definitely_failed:
                error_msg = f"Mustang execution failed (Exit {return_code})"
                if return_code == 139:
                    error_msg += ". This often indicates extreme structural divergence (e.g. Collagen vs Globular). Try removing structurally atypical proteins."

                logger.error(f"Mustang failed (Exit {return_code}).")
                return False, error_msg, None

            if not pdb_file.exists():
                logger.error("Mustang did not produce alignment.pdb")
                return False, "Mustang did not produce alignment.pdb", None

            # Standardize FASTA output name
            # Mustang produces .afasta or .fasta
            if not fasta_file.exists():
                if afasta_file.exists():
                    shutil.copy(afasta_file, fasta_file)
                else:
                    # Check for .fasta (Mustang sometimes uses this)
                    possible_fasta = list(output_dir.glob("*.fasta"))
                    if possible_fasta and possible_fasta[0].name != "alignment.fasta":
                        shutil.copy(possible_fasta[0], fasta_file)
                    elif not possible_fasta:
                        logger.error("Mustang did not produce alignment fasta")
                        return False, "Mustang did not produce alignment fasta", None

            # CALCULATE RMSD MATRIX (Python Native)
            try:
                from src.backend.rmsd_calculator import calculate_structure_rmsd

                logger.info("Computing RMSD matrix using Native Python calculator...")
                rmsd_df = calculate_structure_rmsd(
                    pdb_file, output_dir / "alignment.fasta"
                )

                if rmsd_df is not None:
                    rmsd_path = output_dir / "rmsd_matrix.csv"
                    rmsd_df.to_csv(rmsd_path)
                    logger.info(f"RMSD matrix saved to {rmsd_path}")
                else:
                    logger.warning("RMSD Calculation returned None")
            except Exception as e:
                logger.error(f"Failed to compute RMSD: {e}")
                # Don't fail the whole run, just missing RMSD

            logger.info("Mustang alignment completed successfully")
            return True, "Alignment completed", output_dir

        except subprocess.TimeoutExpired:
            return False, f"Mustang timed out after {self.timeout}s", None
        except Exception as e:
            logger.error(f"Mustang execution error: {str(e)}")
            return False, f"Mustang error: {str(e)}", None

    def _convert_to_wsl_path(self, windows_path: Path) -> str:
        """
        Convert Windows path to WSL path format.

        Args:
            windows_path: Windows Path object

        Returns:
            WSL-compatible path string

        Example:
            C:\\Users\\akash\\file.pdb -> /mnt/c/Users/akash/file.pdb
        """
        path_str = str(windows_path.absolute())

        # Convert backslashes to forward slashes
        path_str = path_str.replace("\\", "/")

        # Convert drive letter (C: -> /mnt/c)
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            path_str = f"/mnt/{drive}{path_str[2:]}"

        return path_str
