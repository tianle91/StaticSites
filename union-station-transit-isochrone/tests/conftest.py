"""Make the repo root importable so tests can `import fetch_isochrones` etc."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
