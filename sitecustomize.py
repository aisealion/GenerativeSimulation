import os, sys
repo = os.path.abspath(os.path.dirname(__file__))
if repo not in sys.path:
    sys.path.insert(0, repo)
