import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import os
import asyncio

app = FastAPI()

NODES = {
    "node1": os.environ.get("NODE1_URL", "http://localhost:8001"),
    "node2": os.environ.get("NODE2_URL", "http://localhost:8002"),
    "node3": os.environ.get("NODE3_URL", "http://localhost:8003"),
}

PRIMARY_NODE = "node1"
MAX_RETRIES  = 3


class QueryRequest(BaseModel):
    sql: str


async def forward(url: str, payload: dict, retries: int = MAX_RETRIES):
    """Forward a request with timeout and retry logic."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        except httpx.ConnectError as e:
            last_error = f"Connection refused (attempt {attempt}/{retries})"
        except httpx.TimeoutException:
            last_error = f"Timeout (attempt {attempt}/{retries})"
        if attempt < retries:
            await asyncio.sleep(0.5)
    return {"error": last_error, "status_code": 503}


@app.post("/query")
async def query(req: QueryRequest):
    url = NODES[PRIMARY_NODE] + "/query"
    return await forward(url, {"sql": req.sql})


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
        "routing":     "static",
        "primary":     PRIMARY_NODE,
        "nodes":       list(NODES.keys()),
        "node_urls":   NODES,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("coordinator:app", host="0.0.0.0", port=port, reload=False)
