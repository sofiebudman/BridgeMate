"""Vercel serverless entry point for Flask app."""
import sys
from pathlib import Path

# Add src directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import app

# Vercel expects the app to be named 'app'
app = app
