import os
from pathlib import Path
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "atlas.sqlite3"
API_KEY = os.getenv("API_KEY", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
MAX_BYTES = 2 * 1024 * 1024
