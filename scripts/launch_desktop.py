"""
StructScope Desktop Launcher
============================
Launches StructScope as a private, high-performance local application.
Automatically opens your default web browser to the local application.
"""

import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_banner():
    banner = """
 ================================================================
   🧬 StructScope Desktop Edition — Local & Private Engine
 ================================================================
   • Status:  Local Server Active
   • Address: http://127.0.0.1:8000
   • Privacy: 100% Local (No external cloud uploads)
   • Compute: Unrestricted local CPU/GPU processing
 ================================================================
   Press Ctrl+C at any time to shut down the local server.
 ================================================================
    """
    print(banner)


def _open_browser_delayed():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")


def main():
    try:
        import uvicorn
    except (ImportError, AttributeError):
        uvicorn = None

    if uvicorn is None:
        print("ERROR: 'uvicorn' is not installed. Please run:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
        return

    static_index = PROJECT_ROOT / "static" / "index.html"
    if not static_index.exists():
        print("WARNING: static/index.html not found.")
        print("Please build the frontend first by running:")
        print("  cd web-frontend && npm run build\n")

    print("Starting StructScope Desktop server on http://127.0.0.1:8000 ...")

    threading.Thread(target=_open_browser_delayed, daemon=True).start()

    print_banner()

    try:
        uvicorn.run(
            "src.backend.api:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\nStructScope Desktop closed. Goodbye!")


if __name__ == "__main__":
    main()
