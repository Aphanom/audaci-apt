import pytest
import sqlite3
import os
import shutil
from unittest.mock import patch

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Setup a temporary directory for test covers and DB
    test_dir = os.path.join(os.getcwd(), "tests", "test_data")
    os.makedirs(test_dir, exist_ok=True)
    
    test_db_path = os.path.join(test_dir, "test_audaci.db")
    test_covers_dir = os.path.join(test_dir, "test_covers")
    os.makedirs(test_covers_dir, exist_ok=True)

    # Patch DB_PATH and COVERS_DIR in the actual modules
    with patch("core.db.DB_PATH", test_db_path), \
         patch("core.metadata_handler.COVERS_DIR", test_covers_dir):
        yield
    
    # Cleanup after all tests
    # shutil.rmtree(test_dir) # Optional: keep it for debugging if needed

@pytest.fixture
def db_conn():
    import core.db as db
    db.init_db()
    conn = db.get_connection()
    yield conn
    conn.close()
