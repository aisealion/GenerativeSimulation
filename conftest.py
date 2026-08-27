import os, sys
# Ensure the repository root is on the Python import path for pytest collection.
repo_root = os.path.abspath(os.path.dirname(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
