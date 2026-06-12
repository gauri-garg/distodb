import subprocess
import sys
import time

def run_cluster():
    processes = []
    nodes = [
        {
            "id": "node1",
            "port": 5001,
            "data_dir": "data/node1",
            "peers": "http://localhost:5002,http://localhost:5003"
        },
        {
            "id": "node2",
            "port": 5002,
            "data_dir": "data/node2",
            "peers": "http://localhost:5001,http://localhost:5003"
        },
        {
            "id": "node3",
            "port": 5003,
            "data_dir": "data/node3",
            "peers": "http://localhost:5001,http://localhost:5002"
        }
    ]

    print("=========================================================")
    print("Launching DistoDB Replicated Cluster (3 Nodes)...")
    print("Nodes will run on ports: 5001, 5002, 5003")
    print("Press Ctrl+C in this terminal to terminate the cluster.")
    print("=========================================================")
    sys.stdout.flush()
    
    try:
        for node in nodes:
            cmd = [
                sys.executable,
                "node/server.py",
                "--node-id", node["id"],
                "--port", str(node["port"]),
                "--data-dir", node["data_dir"],
                "--peers", node["peers"]
            ]
            # Start node process
            p = subprocess.Popen(cmd)
            processes.append(p)
            time.sleep(0.3)

        # Keep running to monitor processes
        while True:
            # Check if any child died unexpectedly
            for p in processes:
                if p.poll() is not None:
                    print("\n[Launcher] Error: A cluster node exited unexpectedly.")
                    raise KeyboardInterrupt()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down cluster nodes...")
        for p in processes:
            p.terminate()
        for p in processes:
            # Wait for clean termination
            p.wait()
        print("[Launcher] All cluster nodes stopped.")
        sys.stdout.flush()

if __name__ == "__main__":
    run_cluster()
