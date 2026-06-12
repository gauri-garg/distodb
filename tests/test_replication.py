import pytest
import subprocess
import sys
import time
import json
import urllib.request
import urllib.error

def get_free_port():
    import socket
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture
def cluster(tmp_path):
    port1 = get_free_port()
    port2 = get_free_port()
    
    dir1 = str(tmp_path / "node1")
    dir2 = str(tmp_path / "node2")
    
    peer1 = f"http://localhost:{port1}"
    peer2 = f"http://localhost:{port2}"
    
    # Start node 1 in background
    p1 = subprocess.Popen([
        sys.executable, "node/server.py",
        "--port", str(port1),
        "--node-id", "node1",
        "--data-dir", dir1,
        "--peers", peer2
    ])
    
    # Start node 2 in background
    p2 = subprocess.Popen([
        sys.executable, "node/server.py",
        "--port", str(port2),
        "--node-id", "node2",
        "--data-dir", dir2,
        "--peers", peer1
    ])
    
    # Wait for both nodes to initialize their sockets and start up
    time.sleep(1.2)
    
    yield (peer1, peer2)
    
    # Clean up subprocesses
    p1.terminate()
    p2.terminate()
    p1.wait()
    p2.wait()

def test_replication_create_insert_delete(cluster):
    peer1, peer2 = cluster
    
    def send_query(peer, sql):
        req_data = json.dumps({"sql": sql}).encode("utf-8")
        req = urllib.request.Request(
            f"{peer}/query",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as res:
            return json.loads(res.read().decode("utf-8"))

    # 1. Create a table on Node 1. This should replicate to Node 2 automatically.
    res = send_query(peer1, "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(20), active BOOL)")
    assert res.get("ok") is True

    # Brief delay for replication to execute on Node 2
    time.sleep(0.3)

    # 2. Query Node 2 to check if the table was successfully created there (empty result but OK status).
    res = send_query(peer2, "SELECT * FROM users")
    assert res.get("ok") is True
    assert res.get("count") == 0

    # 3. Insert a row on Node 1 (using boolean literal and VARCHAR).
    res = send_query(peer1, 'INSERT INTO users (id, name, active) VALUES (1, "Alice", TRUE)')
    assert res.get("ok") is True

    time.sleep(0.3)

    # 4. Query Node 2 and assert that the inserted row is replicated!
    res = send_query(peer2, "SELECT * FROM users WHERE id = 1")
    assert res.get("ok") is True
    assert res.get("count") == 1
    assert res.get("rows")[0]["name"] == "Alice"
    assert res.get("rows")[0]["active"] is True

    # 5. Insert another row with type coercion on Node 1.
    res = send_query(peer1, 'INSERT INTO users (id, name, active) VALUES (2, 999, "no")')
    assert res.get("ok") is True

    time.sleep(0.3)

    # 6. Verify replication on Node 2 and check type coercions are preserved.
    res = send_query(peer2, "SELECT * FROM users WHERE id = 2")
    assert res.get("ok") is True
    assert res.get("rows")[0]["name"] == "999"
    assert res.get("rows")[0]["active"] is False

    # 7. Delete a row on Node 1.
    res = send_query(peer1, "DELETE FROM users WHERE id = 1")
    assert res.get("ok") is True

    time.sleep(0.3)

    # 8. Verify the deletion replicated to Node 2.
    res = send_query(peer2, "SELECT * FROM users WHERE id = 1")
    assert res.get("count") == 0
    
    # Still should have the other row
    res = send_query(peer2, "SELECT * FROM users")
    assert res.get("count") == 1
