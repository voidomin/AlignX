# Windows Installation Guide for Mustang Pipeline

## Overview

This guide provides step-by-step instructions for setting up all required tools on **Windows 10/11** for the automated Mustang bioinformatics pipeline.

## ⚠️ Important: Mustang on Windows

**Mustang has NO native Windows binaries.** You have two options:

### Option A: WSL (Windows Subsystem for Linux) - **RECOMMENDED**

Run Mustang in a Linux environment within Windows. Best compatibility.

###Option B: Bio3D R Package
Use Python to call R's Bio3D package, which wraps Mustang. Simpler but requires R installation.

**Our pipeline will support BOTH options** - you choose during setup.

---

## Installation Steps

### 1. Install Python 3.10+

1. Download Python from: https://www.python.org/downloads/
2. **CRITICAL**: Check "Add Python to PATH" during installation
3. Verify installation:
   ```powershell
   python --version
   # Should show: Python 3.10.x or higher
   ```

---

### 2. Install Mustang (Choose ONE option)

#### **Option A: WSL + Mustang (Recommended for accuracy)**

**Step 1: Enable WSL**

```powershell
# Open PowerShell as Administrator
wsl --install
# Restart your computer
```

**Step 2: Install Ubuntu from Microsoft Store**

- Open Microsoft Store
- Search "Ubuntu 22.04 LTS"
- Install and launch
- Set up username/password

**Step 3: Install Mustang in WSL**

```bash
# Inside Ubuntu terminal
sudo apt update
sudo apt install -y build-essential wget

# Download Mustang
cd ~
wget http://lcb.infotech.monash.edu.au/mustang/mustang_v3.2.3.tgz
tar -xzf mustang_v3.2.3.tgz
cd MUSTANG_v.3.2.3

# Compile
make

# Test installation
./bin/mustang -h
# Should show help message

# Add to PATH
echo 'export PATH=$PATH:~/MUSTANG_v.3.2.3/bin' >> ~/.bashrc
source ~/.bashrc
```

**Step 4: Configure pipeline to use WSL**
Our pipeline will automatically detect WSL and call `wsl mustang` when needed.

---

#### **Option B: Bio3D R Package (Simpler setup)**

**Step 1: Install R**

1. Download R from: https://cran.r-project.org/bin/windows/base/
2. Install with default settings
3. Verify:
   ```powershell
   R --version
   ```

**Step 2: Install Bio3D package**

```powershell
# Open R console
R
```

```r
# Inside R console
install.packages("bio3d")

# Test Mustang availability
library(bio3d)
# If it complains about Mustang, the package will guide you
```

**Step 3: Install rpy2 (Python-R bridge)**

```powershell
pip install rpy2
```

Our pipeline will call R's Bio3D functions from Python transparently.

---

### 3. Install Phylip

**Good news: Native Windows executables available!**

**Step 1: Download Phylip**

- Go to: https://evolution.genetics.washington.edu/phylip/getme-new1.html
- Download **phylip-3.698-win-64bit.zip** (or 32-bit if needed)

**Step 2: Extract and setup**

```powershell
# Extract to C:\phylip
# Add to PATH
$env:Path += ";C:\phylip\exe"

# Make permanent (System Properties > Environment Variables > Path > Add C:\phylip\exe)
```

**Step 3: Verify**

```powershell
neighbor
# Should show Phylip neighbor program menu
```

---

### 4. Install PyMOL

**Option A: Conda (Recommended)**

```powershell
# Install Miniconda
# Download from: https://docs.conda.io/en/latest/miniconda.html

# Create environment
conda create -n pymol-env python=3.11 pip
conda activate pymol-env

# Install PyMOL
conda install -c conda-forge pymol-open-source


# Test
pymol
# Should launch PyMOL window
```

**Option B: Pip with wheel files**

```powershell
# Download wheels from: https://github.com/cgohlke/pymol-open-source-wheels/releases

# Install
pip install numpy-*.whl
pip install pymol-*.whl

# Test
python -m pymol
```

---

### 5. Install FigTree (Optional - for manual tree viewing)

**Native Windows application available!**

1. Download from: https://github.com/rambaut/figtree/releases
2. Download **FigTree_v1.4.4.zip**
3. Extract and run `FigTree.exe`

_Note: Our pipeline can generate tree images without FigTree, so this is optional._

---

### 6. Install Pipeline Dependencies

```powershell
# Navigate to pipeline directory
cd "c:\Users\akash\Documents\project\projects bio\mustang_pipeline"

# Install Python packages
pip install -r requirements.txt
```

---

## Installation Verification

Run our setup checker:

```powershell
python main.py --check-setup
```

Expected output:

```
🔍 Checking Pipeline Setup...

✓ Python 3.11.5 detected
✓ Mustang available (via WSL/Bio3D)
✓ Phylip neighbor found
✓ PyMOL installed
⚠ FigTree not found (optional)
✓ All Python packages installed

🎉 Setup complete! Ready to run pipeline.
```

---

## Choosing Between Mustang Options

| Feature              | WSL + Mustang             | Bio3D R Package                |
| -------------------- | ------------------------- | ------------------------------ |
| **Performance**      | Faster                    | Slightly slower                |
| **Accuracy**         | Direct Mustang            | Same (uses Mustang internally) |
| **Setup Complexity** | Moderate (enable WSL)     | Simple (install R)             |
| **Disk Space**       | ~2 GB (WSL)               | ~500 MB (R)                    |
| **Best For**         | Users familiar with Linux | R users, quick setup           |

**Recommendation**: If you'll use this pipeline long-term, go with **WSL + Mustang**. Otherwise, **Bio3D** is fine for getting started quickly.

---

## Troubleshooting

### "wsl command not found"

- WSL not enabled. Run `wsl --install` as Administrator and restart.

### "Phylip neighbor not found"

- PATH not set correctly. Verify `C:\phylip\exe` is in system PATH.

### "PyMOL import error"

- Wrong wheel file version. Ensure it matches your Python version (e.g., cp311 for Python 3.11).

### "R not found" (Bio3D option)

- R not in PATH. Reinstall R and check "Add to PATH" option.

---

## Next Steps

After installation complete:

1. Test with example dataset: `python main.py --example gpcr`
2. Run interactive setup: `python main.py --interactive`
3. Read full documentation: `README.md`

---

## Need Help?

Installation checker output guides you to specific fixes. Run:

```powershell
python main.py --check-setup --verbose
```

This will provide detailed diagnostic information and suggest solutions.
