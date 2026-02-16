# Deployment Guide for Mustang Pipeline

This guide explains how to deploy your Mustang Pipeline web application to the cloud for free, so you can share it with colleagues or access it from anywhere.

## ☁️ Option 1: Streamlit Community Cloud (Recommended)

Streamlit Cloud is the easiest way to deploy Streamlit apps. It connects directly to your GitHub repository.

### Prerequisites

1.  A [GitHub account](https://github.com/).
2.  Your project pushed to a GitHub repository (public or private).

### Steps

1.  **Push your code to GitHub**:

    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    git branch -M main
    git remote add origin https://github.com/YOUR_USERNAME/mustang-pipeline.git
    git push -u origin main
    ```

2.  **Sign up/Login to Streamlit Cloud**:
    - Go to [share.streamlit.io](https://share.streamlit.io/).
    - Sign in with GitHub.

3.  **Deploy the App**:
    - Click "New app".
    - Select your repository (`mustang-pipeline`).
    - Branch: `main`.
    - Main file path: `app.py`.
    - Click **"Deploy!"**.

4.  **Wait for Build**:
    - Streamlit will install dependencies from `requirements.txt`.
    - Once finished, your app will be live at `https://mustang-pipeline-yourname.streamlit.app`.

### ✨ Automated Mustang Setup

In v1.1.2, the pipeline is fully automated for cloud environments:

1.  **Auto-Compile**: The app automatically detects the Linux environment and compiles the bundled Mustang source code if a binary isn't pre-installed.
2.  **Platform Agnostic**: All file path conversions and WSL-specific logic are automatically bypassed.
3.  **Dependency Synchronization**: The included `packages.txt` provides all system-level build tools needed for the compilation.

### ⚠️ Note on Persistent History

Streamlit Community Cloud uses ephemeral storage. This means:

- The **"History"** sidebar will be cleared if the server reboots.
- **Result Files** will be cleared on server restart.
- **Recommendation**: Download your results and alignment files from the "Downloads" tab for permanent storage.

---

## 🤗 Option 2: Hugging Face Spaces

Hugging Face Spaces offers a simple way to host ML demos.

1.  **Create a Space**:
    - Go to [huggingface.co/spaces](https://huggingface.co/spaces).
    - Click "Create new Space".
    - Name: `mustang-pipeline`.
    - SDK: **Streamlit**.

2.  **Upload Code**:
    - Clone the Space repository to your computer.
    - Copy your project files into it.
    - `git add .`, `git commit`, `git push`.

3.  **Dependencies**:
    - Ensure `requirements.txt` is present.
    - Hugging Face will auto-install them.

---

## 🔒 Configuration (Secrets)

If you add features requiring API keys (e.g., if we added OpenAI for summaries), set them in the platform's secrets manager:

- **Streamlit**: App Dashboard -> Settings -> Secrets.
- **Hugging Face**: Space Settings -> Repository secrets.
