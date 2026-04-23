# scripts/tests/conftest.py
import sys
from pathlib import Path

# Make `scripts/` importable so `from schemas import ...` works inside tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
