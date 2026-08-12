import hashlib
import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from node.hash_ring import HashRing
import os
import asyncio
import re

app = FastAPI()

NODES = {
    "node1": os.environ.get("NODE1_URL", "http://localhost:8001"),
    "node2": os.environ.get("NODE2_URL", "http://localhost:8002"),
    "node3": os.environ.get("NODE3_URL", "http://localhost:8003"),
}

MAX_RETRIES = 3

# Build the hash ring with all 3 nodes
ring = HashRing()
for name in NODES:
    ring.add_node(name)


class QueryRequest(BaseModel):
    sql: str


def extract_key(sql: str) -> str:
    """
    Extract the routing key from a SQL statement.
    For INSERT/SELECT/UPDATE/DELETE with WHERE id = X → use X as key.
    For SELECT * (no WHERE) → return None (scatter-gather needed later).
    For CREATE TABLE → use table name as key.
    """
    sql_lower = sql.strip().lower()

    # WHERE id = <value>  or  WHERE id = '<value>'
    match = re.search(r"where\s+\w+\s*=\s*['\"]?(\w+)['\"]?", sql_lower)
    if match:
        return match.group(1)

    # INSERT INTO table (id, ...) VALUES (value, ...)
    match = re.search(r"values\s*\(\s*['\"]?(\w+)['\"]?", sql_lower)
    if match:
        return match.group(1)

    # CREATE TABLE name → route by table name
    match = re.search(r"create\s+table\s+(\w+)", sql_lower)
    if match:
        return match.group(1)

    # UPDATE table → route by table name
    match = re.search(r"update\s+(\w+)", sql_lower)
    if match:
        return match.group(1)

    # SELECT without WHERE → use table name (will be scatter-gather in Week 10)
    match = re.search(r"from\s+(\w+)", sql_lower)
    if match:
        return match.group(1)

    return "default"


async def forward(url: str, payload: dict, retries: int = MAX_RETRIES):
    """Forward request with timeout and retry."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        except httpx.ConnectError:
            last_error = f"Connection refused (attempt {attempt}/{retries})"
        except httpx.TimeoutException:
            last_error = f"Timeout (attempt {attempt}/{retries})"
        if attempt < retries:
            await asyncio.sleep(0.5)
    return {"error": last_error, "status_code": 503}


@app.post("/query")
async def query(req: QueryRequest):
    key      = extract_key(req.sql)
    node     = ring.get_node(key)
    url      = NODES[node] + "/query"
    result   = await forward(url, {"sql": req.sql})
    result["routed_to"] = node
    result["routing_key"] = key
    return result


@app.get("/health")
async def health():
    status = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in NODES.items():
            try:
                resp = await client.get(url + "/health")
                status[name] = resp.json()
            except Exception:
                status[name] = {"status": "unreachable"}
    return {"coordinator": "ok", "nodes": status}


@app.get("/status")
async def status():
    return {
        "coordinator": "ok",
        "routing":     "consistent_hashing",
        "nodes":       list(NODES.keys()),
        "node_urls":   NODES,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("coordinator:app", host="0.0.0.0", port=port, reload=False)
