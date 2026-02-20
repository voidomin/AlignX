import subprocess
import shutil
import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import re
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger()


class MustangRunner:
    """Wrapper for running Mustang structural alignment."""
    
    def __init__(self, config: Dict):
        """
        Initialize Mustang Runner.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        self.backend = config.get('mustang', {}).get('backend', 'auto')
        self.executable = config.get('mustang', {}).get('executable_path', None)
        self.timeout = config.get('mustang', {}).get('timeout', 600)
        
        # Platform detection
        self.is_linux = sys.platform.startswith('linux')
        self.is_windows = sys.platform.startswith('win')
        self.use_wsl = False # Default
        
        logger.info(f"Initialized Mustang Runner (Platform: {sys.platform}, Mode: {self.backend})")
    

    def _compile_from_source(self) -> bool:
        """Attempt to compile Mustang from bundled source."""
        try:
            logger.info("Attempting to compile Mustang from bundled source...")
            
            # Check for bundled tarball
            bundled_tarball = Path("mustang.tgz")
            if not bundled_tarball.exists():
                logger.error("Bundled mustang.tgz not found!")
                return False

            build_dir = Path("mustang_build")
            if build_dir.exists():
                try:
                    shutil.rmtree(build_dir)
                except Exception as e:
                    logger.warning(f"Could not clear existing build directory (might be in use): {e}. Attempting to proceed...")
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
            if self.is_windows and shutil.which('wsl'):
                use_wsl_for_make = True
                
            if use_wsl_for_make:
                logger.info("Compiling with make inside WSL...")
                subprocess.run(["wsl", "make"], cwd=str(src_dir.absolute()), check=True, timeout=300)
            else:
                logger.info(f"Compiling with native make on {sys.platform}...")
                subprocess.run(["make"], cwd=str(src_dir.absolute()), check=True, timeout=300)
            
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
                        os.chmod(self.executable, 0o755) # Ensure executable
                    return True
            
            logger.error("Compilation finished but binary not found")
            return False
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False





    def _check_mustang(self) -> Tuple[bool, str]:
        """Check if Mustang binary is available (Native, WSL, or Built)."""
        # 1. Check Native (Windows or Linux)
        if hasattr(self, 'mustang_path') and self.mustang_path.exists():
            try:
                subprocess.run([str(self.mustang_path), '--help'], capture_output=True, timeout=2)
                self.use_wsl = False
                return True, f"Mustang binary found (Native {sys.platform})"
            except Exception:
                pass 
        
        # 2. Check System-wide WSL Binary (Only on Windows)
        if self.is_windows:
            try:
                res = subprocess.run(['wsl', 'which', 'mustang'], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    self.use_wsl = True
                    self.mustang_path = Path('mustang') 
                    return True, "System Mustang binary found (WSL)"
            except Exception:
                pass

        # 3. Check Compiled Binary (Search build path)
        build_dir = self.base_dir / 'mustang_build'
        if build_dir.exists():
            binaries = list(build_dir.glob("**/bin/mustang*"))
            if binaries:
                bin_path = binaries[0]
                if self.is_windows:
                    try:
                        wsl_str = self._convert_to_wsl_path(bin_path)
                        res = subprocess.run(['wsl', wsl_str, '--help'], capture_output=True, timeout=5)
                        if res.returncode != 127:
                            self.use_wsl = True
                            self.mustang_path = bin_path
                            return True, "Compiled Mustang found (WSL)"
                    except Exception:
                        pass
                else:
                    # Linux Native
                    try:
                        os.chmod(bin_path, 0o755)
                        subprocess.run([str(bin_path), '--help'], capture_output=True, timeout=2)
                        self.use_wsl = False
                        self.mustang_path = bin_path
                        return True, "Compiled Mustang found (Native Linux)"
                    except Exception:
                        pass
                
        return False, "Mustang binary not found"


    def _install_bio3d(self) -> bool:
        """Attempt to install Bio3D package dynamically."""
        try:
            logger.info("Attempting to auto-install 'bio3d' R package...")
            install_script = 'install.packages("bio3d", repos="https://cloud.r-project.org")'
            
            # Use detected R executable if available
            r_cmd = getattr(self, 'r_executable', 'R')
            
            subprocess.run([r_cmd, '--vanilla', '-e', install_script], 
                         check=True, timeout=300)
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to auto-install Bio3D: {e}")
            return False
            
    @property
    def base_dir(self):
        """Lazy load base_dir to handle stale session state."""
        if not hasattr(self, '_base_dir'):
             self._base_dir = Path(__file__).resolve().parent.parent.parent
        return self._base_dir

    def check_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is properly installed with fallbacks."""
        
        # 1. Check if 'mustang' is in PATH (Native)
        if shutil.which('mustang'):
             self.backend = 'native'
             self.executable = 'mustang'
             return True, "Found native Mustang binary in PATH"

        # 2. Check System-wide WSL Binary (Only on Windows)
        if self.is_windows:
            try:
                # Direct check for mustang in WSL
                # Note: WSL output might be UTF-16 in some terminals, leading to \x00 bytes
                # Increased timeout to 30s as WSL might need to spin up (cold start)
                res = subprocess.run(['wsl', 'which', 'mustang'], capture_output=True, timeout=30)
                
                # Robust decoding
                try:
                    stdout_str = res.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    stdout_str = res.stdout.decode('utf-16', errors='ignore')
                    
                # Clean up null bytes if any remain
                stdout_str = stdout_str.replace('\x00', '').strip()
                
                if res.returncode == 0 and stdout_str and 'mustang' in stdout_str:
                    self.use_wsl = True
                    self.mustang_path = Path('mustang') 
                    # Force backend to wsl if it was auto OR bio3d (prioritize native)
                    if self.backend in ['auto', 'bio3d']:
                        self.backend = 'wsl'
                    logger.info(f"System Mustang binary found in WSL: {stdout_str}")
                    return True, "System Mustang binary found (WSL)"
                else:
                    logger.warning(f"WSL check failed. 'wsl which mustang' returned: '{stdout_str}' (Exit: {res.returncode})")
            except Exception as e:
                logger.warning(f"WSL check exception: {e}")

        # 3. Try to Compile
        if self._compile_from_source():
             # Re-check after compilation
             found, msg = self._check_mustang()
             if found:
                 if getattr(self, 'use_wsl', False):
                     self.backend = 'wsl'
                     if str(self.mustang_path) == 'mustang':
                         self.executable = 'mustang'
                     else:
                         self.executable = self._convert_to_wsl_path(self.mustang_path)
                     return True, "Compiled Mustang binary (WSL)"
                 else:
                     self.backend = 'native'
                     self.executable = str(self.mustang_path)
                     return True, "Compiled Mustang binary (Native)"
             
        # 4. Fallback to Bio3D (Requires R)
        if self.backend != 'bio3d':
            self.backend = 'bio3d'
            
        return self._check_bio3d()

    def _find_r_executable(self) -> Optional[str]:
        """Find R executable with rigorous verification."""
        logger.info("Searching for R executable...")
        
        candidates = []
        
        # 1. Check common Windows locations (Only on Windows)
        if self.is_windows:
            common_paths = [
                r"C:\Program Files\R",
                r"C:\Program Files (x86)\R"
            ]
            
            for base_path_str in common_paths:
                base_path = Path(base_path_str)
                if base_path.exists():
                    try:
                        # Get all R folders, sort by version descending
                        r_installations = [d for d in base_path.iterdir() if d.is_dir()]
                        r_installations.sort(key=lambda x: x.name, reverse=True)
                        
                        for r_dir in r_installations:
                            # Check bin/x64/R.exe
                            bin_x64 = r_dir / "bin" / "x64" / "R.exe"
                            if bin_x64.exists():
                                candidates.append(str(bin_x64))
                                
                            # Check bin/R.exe
                            bin_root = r_dir / "bin" / "R.exe"
                            if bin_root.exists():
                                candidates.append(str(bin_root))
                    except Exception as e:
                        logger.error(f"Error scanning {base_path}: {e}")
        else:
            # 1b. Check common Linux locations
            linux_paths = ["/usr/bin/R", "/usr/local/bin/R", "/usr/lib/R/bin/R"]
            for lp in linux_paths:
                if Path(lp).exists():
                    candidates.append(lp)

        # 2. Check PATH as fallback
        path_r = shutil.which('R')
        if path_r:
            candidates.append(path_r)
            
        # 3. Verify candidates
        for r_path in candidates:
            logger.info(f"Verifying R candidate: {r_path}")
            try:
                # Try running R --version
                # Use strict timeout
                result = subprocess.run(
                    [r_path, '--version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"[OK] Verified R executable: {r_path}")
                    return r_path
                else:
                    logger.warning(f"[FAIL] Candidate {r_path} failed verification (Exit {result.returncode})")
            except Exception as e:
                logger.warning(f"[FAIL] Candidate {r_path} failed execution: {e}")
                
        logger.error("No valid R executable found after checking all candidates.")
        return None

    def _check_bio3d(self) -> Tuple[bool, str]:
        """Check Bio3D R package availability."""
        try:
            r_exec = self._find_r_executable()
            if not r_exec:
                 return False, "R executable not found in PATH or standard locations."
            
            self.r_executable = r_exec # Store for later use
            
            # Check if R is installed
            result = subprocess.run([self.r_executable, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "R not installed. Required for Bio3D backend."
            
            # Check if bio3d package is installed
            check_script = 'if(!require("bio3d", quietly=TRUE)) quit(status=1)'
            result = subprocess.run([self.r_executable, '--vanilla', '-e', check_script],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return True, "Bio3D R package found"
            else:
                # Attempt Auto-Install
                if self._install_bio3d():
                    # Check again
                    result = subprocess.run([self.r_executable, '--vanilla', '-e', check_script],
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return True, "Bio3D R package installed and found"
                
                return False, "Bio3D R package not installed and auto-install failed."
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False, f"R not found: {str(e)}"
    
    def run_alignment(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
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
            
        # Use the local copies for alignment
        if self.backend == 'bio3d':
            return self._run_bio3d_alignment(local_pdb_files, output_dir)
        else:
            return self._run_native_mustang(local_pdb_files, output_dir)
    
    def _construct_command(self, pdb_files: List[Path], output_dir: Path) -> Tuple[List[str], Path]:
        """
        Construct the command line arguments for Mustang.
        Returns: (command_list, run_cwd)
        """
        # We run in output_dir, so we can use filenames directly (files are copied there)
        run_cwd = output_dir.absolute()
        input_filenames = [p.name for p in pdb_files]
        
        output_prefix_arg = 'alignment'

        if getattr(self, 'use_wsl', False):
            cmd = ['wsl', str(self.executable)]
        else:
            # Native execution
            exe_path = Path(self.executable)
            if exe_path.exists():
                cmd = [str(exe_path.resolve())]
            else:
                cmd = [str(self.executable)]

        # Add arguments
        cmd.extend(['-i'] + input_filenames + [
            '-o', output_prefix_arg,
            '-F', 'fasta',
            '-r', 'ON'
        ])
        
        return cmd, run_cwd

    def _run_native_mustang(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """Run native Mustang binary."""
        try:
            cmd, run_cwd = self._construct_command(pdb_files, output_dir)
            
            logger.info(f"Running Mustang: {cmd[:2]}... (CWD: {run_cwd})")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(run_cwd)
            )
            
            if result.returncode != 0:
                logger.error(f"Mustang failed: {result.stderr}")
                return False, f"Mustang execution failed: {result.stderr}", None
            
            # Save stdout to log file for RMSD parsing
            log_file = output_dir / 'mustang.log'
            with open(log_file, 'w') as f:
                f.write(result.stdout)
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr)
            
            # Check for output files - Mustang creates .afasta or .fasta
            afasta_file = output_dir / 'alignment.afasta'
            fasta_file = output_dir / 'alignment.fasta'
            pdb_file = output_dir / 'alignment.pdb'
            
            if not pdb_file.exists():
                 logger.error("Mustang did not produce alignment.pdb")
                 return False, "Mustang did not produce alignment.pdb", None

            # Standardize FASTA output name
            if afasta_file.exists() and not fasta_file.exists():
                shutil.copy(afasta_file, output_dir / 'alignment.fasta')
            elif not fasta_file.exists():
                logger.error("Mustang did not produce alignment fasta")
                return False, "Mustang did not produce alignment fasta", None
            
            # CALCULATE RMSD MATRIX (Python Native)
            try:
                from src.backend.rmsd_calculator import calculate_structure_rmsd
                logger.info("Computing RMSD matrix using Native Python calculator...")
                rmsd_df = calculate_structure_rmsd(pdb_file, output_dir / 'alignment.fasta')
                
                if rmsd_df is not None:
                    rmsd_path = output_dir / 'rmsd_matrix.csv'
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
            
            # Save stdout to log file for RMSD parsing
            log_file = output_dir / 'mustang.log'
            with open(log_file, 'w') as f:
                f.write(result.stdout)
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr)
            
            # Check for output files - Mustang creates .afasta or .fasta
            afasta_file = output_dir / 'alignment.afasta'
            fasta_file = output_dir / 'alignment.fasta'
            html_file = output_dir / 'alignment.html'
            pdb_file = output_dir / 'alignment.pdb'
            
            if not (afasta_file.exists() or fasta_file.exists() or html_file.exists()):
                # Debug info
                all_files = [f.name for f in output_dir.iterdir()]
                log_content = "Log not found"
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        
                error_msg = f"Mustang did not produce expected output files.\nFound: {all_files}\nLog tail: {log_content[-500:]}"
                logger.error(error_msg)
                return False, error_msg, None
            
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
        path_str = path_str.replace('\\', '/')
        
        # Convert drive letter (C: -> /mnt/c)
        if len(path_str) >= 2 and path_str[1] == ':':
            drive = path_str[0].lower()
            path_str = f"/mnt/{drive}{path_str[2:]}"
        
        return path_str
    
    
    def _run_bio3d_alignment(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """Run Mustang via Bio3D R package."""
        try:
            # Create R script
            r_script = output_dir / 'run_mustang.R'
            
            # CRITICAL FIX FOR WINDOWS: R needs forward slashes even on Windows
            # pathlib.absolute() returns backslashes on Windows, which R interprets as escape chars
            pdb_paths_r = ', '.join([f'"{str(p.absolute()).replace(chr(92), "/")}"' for p in pdb_files])
            
            # Also fix output path for R
            output_dir_r = str(output_dir.absolute()).replace(chr(92), "/")
            
            # Handle WSL: Bio3D running in Windows R cannot directly call WSL binary
            # We must create a shim script (wrapper) if we are using WSL
            mustang_exe_arg = ""
            if getattr(self, 'use_wsl', False):
                shim_path = output_dir / 'mustang_shim.bat'
                with open(shim_path, 'w') as f:
                    f.write('@echo off\n')
                    f.write('wsl mustang %*\n')
                
                # Convert shim path for R
                shim_path_r = str(shim_path.absolute()).replace(chr(92), "/")
                mustang_exe_arg = f', exefile="{shim_path_r}"'
                logger.info(f"Created WSL shim at {shim_path}")

            script_content = f"""
library(bio3d)

# Redirect output to log file
sink("mustang.log", split=TRUE)

# PDB files
pdb_files <- c({pdb_paths_r})

# Run Mustang alignment
result <- mustang(pdb_files{mustang_exe_arg})

# Save outputs
write.fasta(result$ali, file="{output_dir_r}/alignment.fasta")
write.csv(result$rmsd, file="{output_dir_r}/rmsd_matrix.csv")

# Save result object
save(result, file="{output_dir_r}/mustang_result.RData")

cat("Mustang alignment completed\\n")

# Close sink
sink()
"""
            
            with open(r_script, 'w') as f:
                f.write(script_content)
            
            # Run R script
            logger.info("Running Mustang via Bio3D R package")
            
            # Use the R executable we found during check_installation
            r_cmd = self.r_executable if hasattr(self, 'r_executable') else 'R'
            
            result = subprocess.run(
                [r_cmd, '--vanilla', '--file', str(r_script)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(output_dir)
            )
            
            if result.returncode != 0:
                # Capture the full output for debugging
                error_msg = f"Bio3D R script failed (Exit Code {result.returncode}).\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                logger.error(error_msg)
                
                # Check for common errors
                if "there is no package called" in result.stderr:
                    return False, "Bio3D package missing in R. Please install it.", None
                
                if "WinError 2" in str(result.stderr) or "WinError 2" in str(result.stdout):
                     return False, "R executable not found or path issue.", None
                     
                return False, error_msg, None
            
            # Check for output
            fasta_file = output_dir / 'alignment.fasta'
            if not fasta_file.exists():
                return False, "Bio3D did not produce expected output", None
            
            logger.info("Bio3D Mustang alignment completed")
            return True, "Alignment completed (Bio3D)", output_dir
            
        except subprocess.TimeoutExpired:
            return False, f"Bio3D timed out after {self.timeout}s", None
        except Exception as e:
            logger.error(f"Bio3D error: {str(e)}")
            return False, f"Bio3D error: {str(e)}", None
    
    def parse_rmsd_matrix(self, output_dir: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
        """
        Parse RMSD matrix from Mustang output.
        
        Args:
            output_dir: Directory containing Mustang outputs
            pdb_ids: List of PDB IDs (for labeling)
            
        Returns:
            DataFrame with RMSD matrix or None if parsing fails
        """
        # Try Bio3D CSV format first
        csv_file = output_dir / 'rmsd_matrix.csv'
        if csv_file.exists():
            try:
                df = pd.read_csv(csv_file, index_col=0)
                df.index = pdb_ids
                df.columns = pdb_ids
                return df
            except Exception as e:
                logger.error(f"Failed to parse CSV RMSD matrix: {str(e)}")
        
        # Try Mustang's .rms_rot file
        rms_rot_file = output_dir / 'alignment.rms_rot'
        if rms_rot_file.exists():
            return self._parse_rms_rot_file(rms_rot_file, pdb_ids)
        
        # Try parsing from Mustang log
        log_file = output_dir / 'mustang.log'
        if log_file.exists():
            return self._parse_mustang_log(log_file, pdb_ids)
        
        logger.error("Could not find RMSD matrix in output")
        return None
    
    def _parse_rms_rot_file(self, rms_rot_file: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
        """
        Parse RMSD matrix from Mustang's .rms_rot file with robust line-based detection.
        """
        try:
            with open(rms_rot_file, 'r') as f:
                content = f.read()
            
            if 'RMSD matrix' not in content:
                logger.error(f"Keyword 'RMSD matrix' not found in {rms_rot_file}")
                return None
                
            lines = content.splitlines()
            matrix_start = None
            for i, line in enumerate(lines):
                if 'RMSD matrix' in line:
                    matrix_start = i
                    break
            
            if matrix_start is None:
                return None
                
            data_rows = []
            for line in lines[matrix_start:]:
                if '|' in line:
                    parts = line.split('|')[1].strip().split()
                    if parts:
                        data_rows.append(parts)
            
            if not data_rows:
                logger.error(f"No data rows found in {rms_rot_file}")
                return None
                
            n = len(pdb_ids)
            matrix = []
            for i in range(min(len(data_rows), n)):
                row = []
                for j in range(min(len(data_rows[i]), n)):
                    val = data_rows[i][j]
                    if val == '---' or '---' in val:
                        row.append(0.0)
                    else:
                        try:
                            row.append(float(val))
                        except ValueError:
                            row.append(0.0)
                while len(row) < n:
                    row.append(0.0)
                matrix.append(row[:n])
            
            while len(matrix) < n:
                matrix.append([0.0] * n)
                
            df = pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
            logger.info(f"Robustly parsed RMSD matrix from {rms_rot_file.name}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to parse .rms_rot file: {str(e)}")
            return None
    
    
    def _parse_mustang_log(self, log_file: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
        """Parse RMSD matrix from Mustang log file using regex patterns."""
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            n = len(pdb_ids)
            potential_matrix = []
            for line in lines:
                matches = re.findall(r'(\d+\.\d+|---)', line)
                if len(matches) == n:
                    row = []
                    for m in matches:
                        if m == '---':
                            row.append(0.0)
                        else:
                            row.append(float(m))
                    potential_matrix.append(row)
            
            if len(potential_matrix) >= n:
                matrix = potential_matrix[-n:]
                df = pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
                logger.info(f"Parsed RMSD matrix from log: {log_file.name}")
                return df
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse Mustang log: {str(e)}")
            return None
