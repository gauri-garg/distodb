import json
import os

WAL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "data.wal")


class WAL:

    def __init__(self, filepath=None):
        if filepath is None:
            self.path = os.path.abspath(WAL_FILE)
        else:
            self.path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def append(self, entry: dict):
        """Write one operation to the WAL and force flush to disk."""
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def read_all(self) -> list:
        """Read every entry from the WAL. Returns [] if file missing."""
        if not os.path.exists(self.path):
            return []
        entries = []
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def clear(self):
        """Wipe the WAL after a successful checkpoint."""
        if os.path.exists(self.path):
            open(self.path, "w").close()
