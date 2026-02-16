#!/bin/bash
# Automated Mustang Installation Script for WSL/Ubuntu
# This script downloads, compiles, and installs Mustang

set -e  # Exit on error

echo "=========================================="
echo "Mustang Installation Script for WSL"
echo "=========================================="
echo ""

# Update system packages
echo "Step 1/5: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install build tools
echo ""
echo "Step 2/5: Installing build essentials and dependencies..."
sudo apt install -y build-essential wget make g++

# Download Mustang
echo ""
echo "Step 3/5: Downloading Mustang v3.2.3..."
cd ~
wget -q --show-progress http://lcb.infotech.monash.edu.au/mustang/mustang_v3.2.3.tgz

# Extract
echo ""
echo "Step 4/5: Extracting and compiling Mustang..."
tar -xzf mustang_v3.2.3.tgz
cd MUSTANG_v.3.2.3

# Compile
make

# Install to /usr/local/bin
echo ""
echo "Step 5/5: Installing Mustang to /usr/local/bin..."
sudo cp bin/mustang /usr/local/bin/
sudo chmod +x /usr/local/bin/mustang

# Verify installation
echo ""
echo "==========================================
echo "Installation Complete!"
echo "=========================================="
echo ""
mustang -h 2>&1 | head -n 5

echo ""
echo "✅ Mustang is now installed and ready to use!"
echo "You can run it from Windows with: wsl mustang"
