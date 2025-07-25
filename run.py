#!/usr/bin/env python3
"""
CircLights startup script
Simple entry point to launch the application with proper initialization
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCircLights stopped by user")
    except Exception as e:
        print(f"Failed to start CircLights: {e}")
        sys.exit(1)