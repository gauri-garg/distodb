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

ring = HashRing()
for name in NODES:
    ring.add_node(name)


class QueryRequest(BaseModel):
    sql: str


def extract_key(sql: str):
    """
    Returns (key, is_scatter) tuple.
    is_scatter=True means SELECT without WHERE — fan out to all nodes.
    """
    sql_lower = sql.strip().lower()

    # WHERE clause present — route to specific node
    match = re.search(r"where\s+\w+\s*=\s*['\"]?(\w+)['\"]?", sql_lower)
    if match:
        return match.group(1), False

    # INSERT — route by first value
    match = re.search(r"values\s*\(\s*['\"]?(\w+)['\"]?", sql_lower)
    if match:
        return match.group(1), False

    # CREATE TABLE — route by table name
    match = re.search(r"create\s+table\s+(\w+)", sql_lower)
    if match:
        return match.group(1), False

    # UPDATE — route by table name
    match = re.search(r"update\s+(\w+)", sql_lower)
    if match:
        return match.group(1), False

    # SELECT without WHERE — scatter-gather
    match = re.search(r"from\s+(\w+)", sql_lower)
    if match:
        return match.group(1), True

    return "default", False


async def forward_one(node_name: str, url: str, payload: dict,
                      retries: int = MAX_RETRIES):
    """Forward to one node with retry."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                return node_name, resp.json()
        except httpx.ConnectError:
            last_error = f"Connection refused (attempt {attempt}/{retries})"
        except httpx.TimeoutException:
            last_error = f"Timeout (attempt {attempt}/{retries})"
        if attempt < retries:
            await asyncio.sleep(0.5)
    return node_name, {"error": last_error, "status_code": 503}


async def scatter_gather(sql: str):
    """
    Fan out to ALL nodes in parallel using asyncio.gather().
    Merge rows from all responses into one result.
    """
    tasks = [
        forward_one(name, url + "/query", {"sql": sql})
        for name, url in NODES.items()
    ]
    results = await asyncio.gather(*tasks)

    all_rows = []
    errors   = []
    for node_name, result in results:
        if "error" in result:
            errors.append(f"{node_name}: {result['error']}")
        elif "rows" in result:
            all_rows.extend(result["rows"])

    response = {
        "ok":           len(errors) == 0,
        "rows":         all_rows,
        "count":        len(all_rows),
        "scatter_nodes": list(NODES.keys()),
    }
    if errors:
        response["errors"] = errors
    return response


@app.post("/query")
async def query(req: QueryRequest):
    key, is_scatter = extract_key(req.sql)

    if is_scatter:
        result = await scatter_gather(req.sql)
        result["routing"] = "scatter_gather"
        return result

    node   = ring.get_node(key)
    url    = NODES[node] + "/query"
    _, result = await forward_one(node, url, {"sql": req.sql})
    result["routed_to"]   = node
    result["routing_key"] = key
    result["routing"]     = "consistent_hash"
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
        "routing":     "consistent_hashing + scatter_gather",
        "nodes":       list(NODES.keys()),
        "node_urls":   NODES,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("coordinator:app", host="0.0.0.0", port=port, reload=False)
