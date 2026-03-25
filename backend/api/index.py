import sys
import os

# Ensure the backend root is on the Python path so `app` package is found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401 — Vercel serverless entry point
