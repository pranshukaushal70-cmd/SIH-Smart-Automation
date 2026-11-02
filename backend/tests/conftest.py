import os
import sys
import tempfile
from pathlib import Path

# Isolated data directory, no auto-seeding: tests never touch the demo database.
_tmp = tempfile.mkdtemp(prefix="veriaicte-test-")
os.environ["VERI_DATA_DIR"] = _tmp
os.environ["VERI_DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["VERI_UPLOAD_DIR"] = str(Path(_tmp) / "uploads")
os.environ["VERI_DEMO_DIR"] = str(Path(_tmp) / "demo")
os.environ["VERI_AUTO_SEED"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
