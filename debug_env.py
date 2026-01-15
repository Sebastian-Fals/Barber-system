import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Version: {sys.version}")
print("Prominent Paths:")
for p in sys.path[:5]:
    print(f" - {p}")

try:
    import yaml
    print(f"SUCCESS: PyYAML imported from {yaml.__file__}")
except ImportError as e:
    print(f"FAILURE: Could not import yaml. {e}")
except Exception as e:
    print(f"FAILURE: Error during import. {e}")
