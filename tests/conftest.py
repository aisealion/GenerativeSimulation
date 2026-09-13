import sys, os
# Add project root to PYTHONPATH for test imports
root = os.path.abspath(os.path.join(__file__, "..", ".."))
if root not in sys.path:
    sys.path.insert(0, root)
