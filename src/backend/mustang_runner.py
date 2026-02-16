"""Mustang wrapper with support for native and Bio3D backends."""

import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import re
import pandas as pd

from ..utils.logger import get_logger

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
        self.executable = config.get('mustang', {}).get('executable_path', 'mustang')
        self.timeout = config.get('mustang', {}).get('timeout', 600)
        
        # Detect which backend to use
        if self.backend == 'auto':
            self.backend = self._detect_backend()
        
        logger.info(f"Mustang backend: {self.backend}")
    
    def _detect_backend(self) -> str:
        """
        Auto-detect available Mustang backend.
        
        Returns:
            'native', 'wsl', or 'bio3d'
        """
        # Try native mustang
        if shutil.which('mustang'):
            logger.info("Detected native Mustang installation")
            return 'native'
        
        # Try WSL mustang
        try:
            result = subprocess.run(['wsl', 'which', 'mustang'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Detected Mustang in WSL")
                self.executable = 'wsl mustang'
                return 'wsl'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fall back to Bio3D
        logger.warning("No native Mustang found, will try Bio3D R package")
        return 'bio3d'
    
    def check_installation(self) -> Tuple[bool, str]:
        """
        Check if Mustang is properly installed.
        
        Returns:
            Tuple of (success, message)
        """
        if self.backend == 'bio3d':
            return self._check_bio3d()
        else:
            return self._check_native_mustang()
    
    def _check_native_mustang(self) -> Tuple[bool, str]:
        """Check native Mustang installation."""
        try:
            cmd = self.executable.split() + ['-h']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 or 'MUSTANG' in result.stdout + result.stderr:
                return True, f"Mustang found: {self.executable}"
            else:
                return False, f"Mustang not responding correctly"
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False, f"Mustang not found: {str(e)}"
    
    def _check_bio3d(self) -> Tuple[bool, str]:
        """Check Bio3D R package availability."""
        try:
            # Check if R is installed
            result = subprocess.run(['R', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "R not installed. Required for Bio3D backend."
            
            # Check if bio3d package is installed
            check_script = 'if(!require("bio3d", quietly=TRUE)) quit(status=1)'
            result = subprocess.run(['R', '--vanilla', '-e', check_script],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return True, "Bio3D R package found"
            else:
                return False, "Bio3D R package not installed. Install with: install.packages('bio3d')"
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False, f"R not found: {str(e)}"

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
                shutil.rmtree(build_dir)
            build_dir.mkdir(exist_ok=True)
            
            # Copy tarball to build dir
            shutil.copy(bundled_tarball, build_dir / "mustang.tgz")
            
            # Extract
            subprocess.run(["tar", "-xzf", "mustang.tgz"], cwd=build_dir, check=True)
            
            # Find makefile directory (it unpacks into a subdir)
            # Handle potential variation in folder name
            extracted_dirs = [d for d in build_dir.iterdir() if d.is_dir()]
            if not extracted_dirs:
                logger.error("Extraction failed: No directory found")
                return False
                
            src_dir = extracted_dirs[0]
            logger.info(f"Source extracted to: {src_dir}")
            
            # Compile using make
            subprocess.run(["make"], cwd=src_dir, check=True)
            
            # Locate binary
            # Mustang makefile typically outputs bin/mustang-x.y.z
            bin_dir = src_dir / "bin"
            if bin_dir.exists():
                binaries = list(bin_dir.glob("mustang*"))
                if binaries:
                    binary = binaries[0]
                    # Copy to local bin or app root
                    target = Path("./mustang")
                    shutil.copy(binary, target)
                    target.chmod(0o755)
                    self.executable = str(target.absolute())
                    logger.info(f"Mustang compiled and installed to {self.executable}")
                    return True
            
            logger.error("Compilation finished but binary not found")
            return False
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False

    def _install_bio3d(self) -> bool:
        """Attempt to install Bio3D package dynamically."""
        try:
            logger.info("Attempting to auto-install 'bio3d' R package...")
            install_script = 'install.packages("bio3d", repos="https://cloud.r-project.org")'
            subprocess.run(['R', '--vanilla', '-e', install_script], 
                         check=True, timeout=300)
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to auto-install Bio3D: {e}")
            return False
            
    def check_installation(self) -> Tuple[bool, str]:
        """Check if Mustang is properly installed with fallbacks."""
        # 1. Check Native/Conda
        if shutil.which('mustang'):
             return True, "Found native Mustang binary"
             
        # 2. Check Local Compilation
        if Path("./mustang").exists():
            self.executable = "./mustang"
            return True, "Found locally compiled Mustang"
            
        # 3. Try to Compile
        if self._compile_from_source():
             return True, "Successfully compiled Mustang from source"
             
        # 4. Fallback to Bio3D (Requires R)
        return self._check_bio3d()

    def _check_bio3d(self) -> Tuple[bool, str]:
        """Check Bio3D R package availability."""
        try:
            # Check if R is installed
            result = subprocess.run(['R', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "R not installed. Required for Bio3D backend."
            
            # Check if bio3d package is installed
            check_script = 'if(!require("bio3d", quietly=TRUE)) quit(status=1)'
            result = subprocess.run(['R', '--vanilla', '-e', check_script],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return True, "Bio3D R package found"
            else:
                # Attempt Auto-Install
                if self._install_bio3d():
                    # Check again
                    result = subprocess.run(['R', '--vanilla', '-e', check_script],
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
        
        if self.backend == 'bio3d':
            return self._run_bio3d_alignment(pdb_files, output_dir)
        else:
            return self._run_native_mustang(pdb_files, output_dir)
    
    def _run_native_mustang(self, pdb_files: List[Path], output_dir: Path) -> Tuple[bool, str, Optional[Path]]:
        """Run native Mustang binary."""
        try:
            # Convert paths for WSL if needed
            if self.backend == 'wsl':
                converted_files = [self._convert_to_wsl_path(p) for p in pdb_files]
                converted_output_dir = self._convert_to_wsl_path(output_dir)
            else:
                converted_files = [str(p.absolute()) for p in pdb_files]
                converted_output_dir = str(output_dir.absolute())
            
            # Output prefix
            if self.backend == 'wsl':
                output_prefix_arg = f"{converted_output_dir}/alignment"
            else:
                output_prefix_arg = str(output_dir / 'alignment')
            
            # Build command - use -i flag with individual files instead of -f with file list
            # This avoids issues with spaces in paths
            cmd = self.executable.split() + ['-i'] + converted_files + [
                '-o', output_prefix_arg,
                '-F', 'fasta',  # Output alignment in FASTA format
                '-r', 'ON',      # Print RMSD table
            ]
            
            logger.info(f"Running Mustang: {' '.join(cmd[:5])}... (with {len(converted_files)} files)")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(output_dir) if self.backend != 'wsl' else None
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
            html_file = output_dir / 'alignment.html'
            pdb_file = output_dir / 'alignment.pdb'
            
            if not (afasta_file.exists() or fasta_file.exists() or html_file.exists()):
                return False, "Mustang did not produce expected output files", None
            
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
            
            pdb_paths_r = ', '.join([f'"{p.absolute()}"' for p in pdb_files])
            
            script_content = f"""
library(bio3d)

# PDB files
pdb_files <- c({pdb_paths_r})

# Run Mustang alignment
result <- mustang(pdb_files)

# Save outputs
write.fasta(result$ali, file="{output_dir}/alignment.fasta")
write.csv(result$rmsd, file="{output_dir}/rmsd_matrix.csv")

# Save result object
save(result, file="{output_dir}/mustang_result.RData")

cat("Mustang alignment completed\\n")
"""
            
            with open(r_script, 'w') as f:
                f.write(script_content)
            
            # Run R script
            logger.info("Running Mustang via Bio3D R package")
            result = subprocess.run(
                ['R', '--vanilla', '--file', str(r_script)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(output_dir)
            )
            
            if result.returncode != 0:
                logger.error(f"Bio3D failed: {result.stderr}")
                return False, f"Bio3D execution failed: {result.stderr}", None
            
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
        Parse RMSD matrix from Mustang's .rms_rot file.
        
        Example format:
        RMSD matrix (based on multiple superpostion):
               1    2    3  
             ---------------
          1|  ---  0.4  0.1
          2|  0.4  ---  0.4
          3|  0.1  0.4  ---
        """
        try:
            with open(rms_rot_file, 'r') as f:
                lines = f.readlines()
            
            # Find the RMSD matrix section
            matrix_start = None
            for i, line in enumerate(lines):
                if 'RMSD matrix' in line:
                    matrix_start = i + 2  # Skip header and column numbers
                    break
            
            if matrix_start is None:
                logger.error("Could not find RMSD matrix in .rms_rot file")
                return None
            
            # Skip the separator line
            matrix_start += 1
            
            # Parse matrix values
            n = len(pdb_ids)
            matrix = []
            
            for i in range(n):
                line = lines[matrix_start + i]
                # Extract values from line like "  1|  ---  0.4  0.1"
                parts = line.split('|')[1].split()
                
                row = []
                for val in parts:
                    if val == '---':
                        row.append(0.0)
                    else:
                        row.append(float(val))
                matrix.append(row)
            
            # Create DataFrame
            df = pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
            logger.info(f"Successfully parsed RMSD matrix from {rms_rot_file.name}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to parse .rms_rot file: {str(e)}")
            return None
    
    
    def _parse_mustang_log(self, log_file: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
        """Parse RMSD matrix from Mustang log file."""
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Look for RMSD matrix in output
            # Mustang typically outputs a matrix of pairwise RMSDs
            # This is a simplified parser - may need adjustment based on actual output
            
            matrix = []
            for line in content.split('\n'):
                # Look for lines containing RMSD values
                numbers = re.findall(r'\d+\.\d+', line)
                if len(numbers) == len(pdb_ids):
                    matrix.append([float(n) for n in numbers])
            
            if len(matrix) == len(pdb_ids):
                df = pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
                return df
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse Mustang log: {str(e)}")
            return None
