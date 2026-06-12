import argparse
import json
import os
import sys
import pathlib
import urllib.request

# Ensure the parent directory is in python search path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))

from http.server import HTTPServer, BaseHTTPRequestHandler
from node.executor import Executor

class NodeHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, node_id, executor, peers):
        super().__init__(server_address, RequestHandlerClass)
        self.node_id = node_id
        self.executor = executor
        self.peers = peers

class NodeHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to log requests to stdout cleanly
        sys.stdout.write(f"[{self.server.node_id}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {
                "node_id": self.server.node_id,
                "peers": self.server.peers,
                "tables": list(self.server.executor.storage.tables.keys())
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path in ("/query", "/replicate"):
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return

            sql = data.get("sql")
            if not sql:
                self.send_error(400, "Missing 'sql' field")
                return

            # Execute query locally
            result = self.server.executor.run(sql)

            # If it is a write query and we are on the /query endpoint, replicate to peers
            if self.path == "/query" and result.get("ok") and self._is_write_query(sql):
                self._replicate_to_peers(sql)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def _is_write_query(self, sql):
        # Clean up whitespace and check if it starts with SELECT
        sql_stripped = sql.strip().lower()
        return not sql_stripped.startswith("select")

    def _replicate_to_peers(self, sql):
        for peer in self.server.peers:
            url = f"{peer}/replicate"
            sys.stdout.write(f"[{self.server.node_id}] Replicating write query to peer: {url}\n")
            sys.stdout.flush()
            try:
                req_data = json.dumps({"sql": sql}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json"}
                )
                # 2-second timeout to prevent blocking indefinitely
                with urllib.request.urlopen(req, timeout=2) as res:
                    res_body = res.read().decode("utf-8")
                    # Optionally log result
            except Exception as e:
                sys.stderr.write(f"[{self.server.node_id}] Warning: Replication to peer {peer} failed: {e}\n")
                sys.stderr.flush()

def run_server():
    parser = argparse.ArgumentParser(description="DistoDB HTTP Server Node")
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

    server_address = ("", args.port)
    httpd = NodeHTTPServer(server_address, NodeHTTPRequestHandler, args.node_id, executor, peers_list)
    print(f"[{args.node_id}] Starting server on port {args.port}...")
    print(f"[{args.node_id}] Data directory: {args.data_dir}")
    print(f"[{args.node_id}] Configured peers: {peers_list}")
    sys.stdout.flush()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{args.node_id}] Shutting down...")
        sys.stdout.flush()
        httpd.server_close()

if __name__ == "__main__":
    run_server()
