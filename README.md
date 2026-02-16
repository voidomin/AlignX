# Mustang Structural Alignment Pipeline

An automated bioinformatics pipeline for multiple structural alignment of **any protein family** using Mustang, with phylogenetic analysis and interactive visualizations.

## 🎯 Features

- ✅ **Universal**: Works with any protein family from PDB
- ✅ **Automated**: One-click analysis from PDB IDs to results
- ✅ **User-Friendly**: Modern web interface (Streamlit)
- ✅ **Flexible Deployment**: Run locally or deploy to cloud (FREE options available)
- ✅ **Smart Filtering**: Handles large PDB files efficiently
- ✅ **Interactive Alignment**: View sequences with conservation highlighting
- ✅ **Residue Analysis**: Identify flexible regions with RMSF plots
- ✅ **Rich Reporting**: Generate professional PDF reports
- ✅ **Metadata**: Auto-fetch protein details (Organism, Method, Resolution)
- ✅ **Complete Pipeline**: Download → Clean → Align → Analyze → Visualize

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Mac/Linux

# Install packages
pip install -r requirements.txt
```

### 2. Install External Tools

See **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)** for detailed instructions on installing:

- Mustang (via WSL or Bio3D R package)
- Phylip (optional, for phylogenetic trees)
- PyMOL (optional, for 3D visualization)

### 3. Run the Application

```bash
# Start Streamlit app
streamlit run app.py

# Opens automatically in browser at http://localhost:8501
```

## 📖 Usage

1. **Enter PDB IDs** or **load an example** (GPCR, Kinases, Lysozymes, etc.)
2. Click **"Run Analysis"**
3. View **RMSD heatmaps**, **clusters**, and **statistics**
4. **Download** results (CSV, PNG, reports)

## 📁 Project Structure

```
mustang_pipeline/
├── app.py                  # Main Streamlit application
├── config.yaml             # Configuration settings
├── requirements.txt        # Python dependencies
├── WINDOWS_SETUP.md        # Installation guide
├── UI_UX_DESIGN.md         # UI layout documentation
├── DEPLOYMENT.md           # Cloud deployment guide
├── src/
│   ├── backend/            # Core processing modules
│   │   ├── pdb_manager.py       # PDB download & cleaning
│   │   ├── mustang_runner.py    # Mustang wrapper
│   │   ├── rmsd_analyzer.py     # RMSD & RMSF analysis
│   │   ├── sequence_viewer.py   # Alignment visualization
│   │   ├── report_generator.py  # PDF reporting
│   │   └── phylo_tree.py        # Phylogenetic analysis
│   └── utils/              # Utilities
│       ├── config_loader.py     # Config management
│       └── logger.py            # Logging
├── examples/               # Example protein datasets
├── data/                   # PDB files (auto-created)
├── results/                # Analysis outputs (auto-created)
└── logs/                   # Log files (auto-created)
```

## 🌐 Deployment Options

### Option 1: Local (Run on Your Computer)

```bash
streamlit run app.py
# Access at: http://localhost:8501
```

### Option 2: Share Temporarily (Ngrok)

```bash
pip install pyngrok
ngrok http 8501
# Get public URL: https://abc123.ngrok.io
```

### Option 3: Deploy to Cloud (FREE)

**Google Cloud Platform** (12 months free, $300 credit):

- See deployment guide in [DEPLOYMENT.md](DEPLOYMENT.md)

**Hugging Face Spaces** (Free forever):

- Push code to Hugging Face
- Auto-deploys at: `https://huggingface.co/spaces/your-username/mustang-pipeline`

## 🔧 Configuration

Edit `config.yaml` to customize:

- PDB download settings
- Mustang backend (native/bio3d)
- Visualization preferences
- Output formats

Or use environment variables (`env.example`).

## 📊 Example Datasets

Included examples:

- **GPCR Channelrhodopsins** (5 proteins)
- **Hemoglobins** (3 proteins)
- **Lysozymes** (3 proteins)
- **Kinases** (3 proteins)

## 🐛 Troubleshooting

### "Mustang not found"

- See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for installation
- Make sure WSL is enabled (Windows) OR Bio3D R package is installed

### "PDB download failed"

- Check internet connection
- Verify PDB ID is correct (4 characters)
- Try again (automatic retry included)

### App won't start

```bash
# Check Python version (3.10+ required)
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## 📝 Citation

If you use this pipeline in your research, please cite:

- **MUSTANG**: Konagurthu AS, Whisstock JC, Stuckey PJ, Lesk AM. MUSTANG: A multiple structural alignment algorithm. Proteins. 2006.
- This pipeline: [Your citation here]

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

MIT License - see LICENSE file

## 🙋 Support

- **Issues**: Open an issue on GitHub
- **Documentation**: See `/docs` folder
- **Examples**: Check `/examples` folder

## 🎓 About

Created as part of a bioinformatics project to automate structural alignment workflows.

**Author**: Akash  
**Version**: 1.0.0  
**Last Updated**: February 2026

---

**Ready to analyze your proteins?** 🧬

```bash
streamlit run app.py
```
