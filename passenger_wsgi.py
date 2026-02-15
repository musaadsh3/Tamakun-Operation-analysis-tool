"""
cPanel Passenger WSGI entry point.
This file is required by cPanel's "Setup Python App" feature.
"""
import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables from .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

from app.main import app

# Passenger expects an 'application' callable (WSGI-compatible).
# FastAPI is ASGI, so we use a2wsgi to bridge ASGI -> WSGI.
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    # Fallback: if a2wsgi is not installed, try uvicorn as ASGI server
    # This won't work with Passenger directly, but handles the import gracefully
    application = app
