import os
import sys
import signal
import subprocess
import json
import shutil
from node.storage import Storage

# Subclass of Storage that crashes on the second save operation
class StorageCrasher(Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_count = 0

    def _save_table(self, name):
        self.save_count += 1
        if self.save_count > 1:
            print("CRASHING_NOW", flush=True)
            sys.stdout.flush()
            # Kill ourselves forcefully with SIGKILL
            os.kill(os.getpid(), signal.SIGKILL)
        else:
            super()._save_table(name)

def run_child(data_dir):
    # Initialize Crasher database
    db = StorageCrasher(data_dir=data_dir)
    # 1. Create table (this will write table metadata and save successfully, since we only crash on insert)
    db.create_table("users", {"id": "INT", "name": "TEXT"}, "id")
    
    # 2. Insert row. During insert, it writes to WAL first, then calls _save_table, which triggers the SIGKILL crash!
    db.insert("users", {"id": 1, "name": "Alice"})

def run_parent():
    data_dir = "data/crash_test"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    
    print("=========================================================")
    print("Starting Crash Test...")
    print("=========================================================")
    sys.stdout.flush()

    # Spawn the child process running this file with --child option
    p = subprocess.Popen([sys.executable, __file__, "--child", data_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for the child to exit (which it should do by killing itself)
    stdout, stderr = p.communicate()
    exit_code = p.returncode
    
    print(f"Child process exited with code: {exit_code} (negative code means killed by signal on Unix)")
    sys.stdout.flush()
    
    # Verify that the child was indeed killed by SIGKILL
    assert exit_code != 0, "Error: Child process did not crash!"
    
    # Now, check the data directory.
    # The JSON file data/crash_test/users.json should contain only the table metadata (no rows),
    # since the crash happened before the insert could save to JSON!
    json_path = os.path.join(data_dir, "users.json")
    wal_path = os.path.join(data_dir, "users.wal")
    
    assert os.path.exists(json_path), "Error: JSON file was not created!"
    assert os.path.exists(wal_path), "Error: WAL file was not created!"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
        print(f"JSON snapshot state before recovery: {json_data['rows']}")
        assert len(json_data["rows"]) == 0, "Error: Rows were written to JSON before the crash!"
        
    with open(wal_path, "r") as f:
        wal_data = f.read()
        print(f"WAL content on disk:\n{wal_data.strip()}")
        assert "insert" in wal_data, "Error: Insert operation was not logged to WAL before crash!"
        
    print("\nStarting a new Storage instance to trigger WAL replay recovery...")
    sys.stdout.flush()
    
    # Start a standard Storage engine. It should read users.json, see non-empty users.wal,
    # replay the insert, save to users.json atomically, and truncate the WAL.
    recovered_db = Storage(data_dir=data_dir)
    
    # Check that users table has been recovered
    assert "users" in recovered_db.tables
    recovered_rows = recovered_db.tables["users"]["rows"]
    print(f"Recovered Rows: {recovered_rows}")
    assert len(recovered_rows) == 1
    assert recovered_rows[0]["id"] == 1
    assert recovered_rows[0]["name"] == "Alice"
    
    # Verify WAL is now truncated (empty)
    assert os.path.getsize(wal_path) == 0, "Error: WAL was not truncated after recovery!"
    
    print("=========================================================")
    print("CRASH RECOVERY TEST SUCCESSFUL!")
    print("=========================================================")
    sys.stdout.flush()
    
    # Clean up
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)

if __name__ == "__main__":
    # Ensure this directory is in path so we can import node
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.resolve()))
    
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        run_child(sys.argv[2])
    else:
        run_parent()
