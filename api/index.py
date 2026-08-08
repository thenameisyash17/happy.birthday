import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your Flask app
from app import app

# Vercel needs this handler
def handler(request, *args, **kwargs):
    return app(request, *args, **kwargs)

# For Python 3.7+ compatibility
application = app