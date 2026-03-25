import sys
import os

# Insert this service's directory at the front of sys.path and clear any
# stale 'main' module cached from another service's test run.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.pop("main", None)
