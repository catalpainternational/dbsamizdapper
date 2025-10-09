"""
Entry point for running dbsamizdat as a module.

Usage:
    python -m dbsamizdat.runner [command] [options]
"""

from .cli import main

if __name__ == "__main__":
    main()
