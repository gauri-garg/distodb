import argparse
import sys
import pathlib
import uvicorn

# Ensure the parent directory is in python search path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))

from node.executor import Executor
from node.api import app

def run_server():
    parser = argparse.ArgumentParser(description="DistoDB FastAPI Node Server")
    parser.add_argument("--port", type=int, default=5001, help="Port to run server on")
    parser.add_argument("--node-id", type=str, default="node1", help="Unique ID of this node")
    parser.add_argument("--data-dir", type=str, default="data/node1", help="Data directory for storage")
    parser.add_argument("--peers", type=str, default="", help="Comma-separated list of peer URLs")
    args = parser.parse_args()

    # Parse peers
    peers_list = []
    if args.peers:
        peers_list = [p.strip() for p in args.peers.split(",") if p.strip()]

    # Initialize Executor for this node
    executor = Executor(data_dir=args.data_dir)

    # Save configuration state in FastAPI app state
    app.state.node_id = args.node_id
    app.state.executor = executor
    app.state.peers = peers_list
    app.state.data_dir = args.data_dir

    print(f"[{args.node_id}] Starting FastAPI server on port {args.port}...")
    print(f"[{args.node_id}] Data directory: {args.data_dir}")
    print(f"[{args.node_id}] Configured peers: {peers_list}")
    sys.stdout.flush()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")

if __name__ == "__main__":
    run_server()
