"""
WSGI entry point for BridgeMate (production).
Used by Gunicorn to serve the Flask application.
"""

import sys
from pathlib import Path

# Ensure the src/ directory is on the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import app  # noqa: E402

if __name__ == "__main__":
    app.run()
