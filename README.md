# DistoDB

A from-scratch distributed SQL database engine built to demonstrate core distributed systems concepts — consistent hashing, Write-Ahead Logging, async replication, and fault-tolerant routing.

> **Educational project.** DistoDB is not intended for production use. It is built to deeply understand how distributed databases work internally.

---

## What it does

- Parses and executes real SQL (SELECT, INSERT, UPDATE, DELETE, CREATE TABLE)
- Stores data on disk with JSON persistence and WAL crash recovery
- Runs as a 3-node HTTP cluster via Docker Compose
- Each node exposes `/query`, `/health`, and `/metrics` endpoints

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| SQL Parsing | Lark 1.3.1 |
| HTTP API | FastAPI + Uvicorn |
| Persistence | JSON + Write-Ahead Log |
| Infrastructure | Docker + Docker Compose |
| Testing | pytest |

---

## Project structure

```
distodb/
├── node/
│   ├── api.py              # FastAPI HTTP server (/query, /health, /metrics)
│   ├── executor.py         # SQL execution engine — walks Lark parse tree
│   ├── parser.py           # Lark SQL parser
│   ├── storage.py          # In-memory + JSON persistence + WAL integration
│   ├── wal.py              # Write-Ahead Log with os.fsync()
│   └── sql_grammar.lark    # SQL grammar definition
├── tests/
│   ├── test_parser.py      # 20+ SQL parser tests
│   └── test_executor.py    # 15+ execution engine tests
├── data/                   # Auto-created — holds data.json and data.wal
├── docker-compose.yml      # 3-node cluster on ports 8001–8003
├── Dockerfile
├── repl.py                 # Interactive SQL REPL
└── requirements.txt
```

---

## Quickstart

### Option 1 — Local REPL (no Docker)

```bash
# Clone and set up
git clone https://github.com/gauri-garg/distodb.git
cd distodb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the interactive SQL shell
python3 repl.py
```

```sql
distodb> CREATE TABLE products (id INT PRIMARY KEY, name TEXT)
distodb> INSERT INTO products (id, name) VALUES (1, "Laptop")
distodb> INSERT INTO products (id, name) VALUES (2, "Phone")
distodb> SELECT * FROM products
distodb> SELECT * FROM products WHERE id = 1
distodb> UPDATE products SET name = "Tablet" WHERE id = 2
distodb> DELETE FROM products WHERE id = 1
distodb> quit
```

### Option 2 — 3-node HTTP cluster (Docker)

```bash
# Start all 3 nodes
docker compose up --build

# In a second terminal — test each node
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## HTTP API

Every node exposes three endpoints:

### POST /query
Execute any SQL statement.

```bash
curl -X POST http://localhost:8001/query \
     -H "Content-Type: application/json" \
     -d '{"sql": "SELECT * FROM products"}'
```

Response:
```json
{"ok": true, "rows": [{"id": 1, "name": "Laptop"}], "count": 1}
```

### GET /health
Check if the node is alive.

```bash
curl http://localhost:8001/health
```

Response:
```json
{"status": "ok", "node_id": "node1"}
```

### GET /metrics
Node statistics.

```bash
curl http://localhost:8001/metrics
```

Response:
```json
{
  "node_id": "node1",
  "queries_total": 12,
  "writes_total": 4,
  "rows_stored": 8,
  "tables": ["products", "users"]
}
```

---

## SQL support

```sql
-- Create a table
CREATE TABLE products (id INT PRIMARY KEY, name TEXT, price FLOAT)

-- Insert rows
INSERT INTO products (id, name, price) VALUES (1, "Laptop", 999.99)

-- Select all
SELECT * FROM products

-- Select with filter
SELECT * FROM products WHERE id = 1
SELECT * FROM products WHERE price > 500

-- Select specific columns
SELECT name, price FROM products

-- Update
UPDATE products SET price = 899.99 WHERE id = 1

-- Delete
DELETE FROM products WHERE id = 1
DELETE FROM products
```

Supported types: `INT`, `TEXT`, `FLOAT`, `VARCHAR(n)`, `BOOL`

Supported operators: `=`, `!=`, `>`, `<`, `>=`, `<=`

---

## How crash recovery works

Every write goes to the WAL before touching the main data file:

```
INSERT row
  → append to data.wal   (os.fsync — guaranteed on disk)
  → update data.json     (main storage)
```

On restart:
```
load data.json  (last clean state)
replay data.wal (recover any writes that didn't reach data.json)
clear data.wal  (checkpoint complete)
```

Kill the process mid-write — data is fully recovered on next start.

---

## Run tests

```bash
python3 -m pytest tests/ -v
```

Expected: **44 passed**

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| SQL Parser | ✅ Done | Lark grammar, 5 statement types |
| Execution Engine | ✅ Done | AST walker, full CRUD |
| JSON Persistence | ✅ Done | Disk storage, survives restarts |
| Write-Ahead Log | ✅ Done | Crash recovery with os.fsync() |
| FastAPI HTTP layer | ✅ Done | /query /health /metrics |
| Docker 3-node cluster | 🔄 In progress | docker compose up |
| Coordinator + routing | ⬜ Planned | Consistent hashing, scatter-gather |
| Replication | ⬜ Planned | Async replica forwarding |
| Failure detection | ⬜ Planned | Heartbeat + auto-failover |
| B-Tree index | ⬜ Planned | O(log n) lookups |
| Query planner | ⬜ Planned | Index scan vs full scan |
| Prometheus metrics | ⬜ Planned | Grafana dashboard |

---

## Key concepts demonstrated

| Concept | Where |
|---|---|
| SQL parsing (Lark EBNF grammar) | `node/sql_grammar.lark`, `node/parser.py` |
| AST tree walking | `node/executor.py` |
| Write-Ahead Logging + fsync | `node/wal.py`, `node/storage.py` |
| Crash recovery via WAL replay | `node/storage.py` → `_recover()` |
| HTTP-based distributed nodes | `node/api.py` |
| Docker bridge networking | `docker-compose.yml` |

---

## Author

Gauri Garg — [github.com/gauri-garg/distodb](https://github.com/gauri-garg/distodb)