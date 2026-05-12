"""
pytest configuration — adds the workspace root to sys.path so that the
project's modules are importable without installing the package.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
