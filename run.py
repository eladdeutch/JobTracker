"""Entry point for running the application."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app
from backend.config import config

if __name__ == '__main__':
    app = create_app()
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           🎯 Job Application Tracker v1.0                      ║
╠═══════════════════════════════════════════════════════════════╣
║  Dashboard: http://{config.HOST}:{config.PORT:<5}                             ║
║  API Docs:  http://{config.HOST}:{config.PORT}/api/health                  ║
╚═══════════════════════════════════════════════════════════════╝
""")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
