
import uvicorn
import httpx
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from node.executor import Executor
import os

NODE_ID  = os.environ.get("NODE_ID", "node1")
PORT     = int(os.environ.get("PORT", 8001))

# Replica URL — the node this node replicates TO
REPLICA_URL = os.environ.get("REPLICA_URL", "")

app      = Executor()
executor = app
metrics  = {"queries_total": 0, "writes_total": 0}

app = FastAPI()
executor = Executor()


class QueryRequest(BaseModel):
    sql: str


async def replicate(sql: str):
    """Forward write to replica node in background — fire and forget."""
    if not REPLICA_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                REPLICA_URL + "/replicate",
                json={"sql": sql}
            )
    except Exception as e:
        print(f"[{NODE_ID}] Replication failed: {e}")


@app.post("/query")
async def query(req: QueryRequest, background_tasks: BackgroundTasks):
    result = executor.run(req.sql)
    metrics["queries_total"] += 1
    sql_lower = req.sql.strip().lower()
    is_write = any(sql_lower.startswith(w)
                   for w in ("insert", "update", "delete", "create"))
    if is_write and "error" not in result:
        metrics["writes_total"] += 1
        background_tasks.add_task(replicate, req.sql)
    return result


@app.post("/replicate")
async def replicate_endpoint(req: QueryRequest):
    """
    Receive a replicated write from another node.
    Execute it silently — do NOT re-replicate (avoid infinite loop).
    """
    result = executor.run(req.sql)
    print(f"[{NODE_ID}] Replicated: {req.sql[:60]} → {result}")
    return {"replicated": True, "result": result}


@app.get("/health")
def health():
    return {"status": "ok", "node_id": NODE_ID}


@app.get("/metrics")
def get_metrics():
    total_rows = sum(
        len(t["rows"]) for t in executor.storage.tables.values()
    )
    return {
        "node_id":       NODE_ID,
        "queries_total": metrics["queries_total"],
        "writes_total":  metrics["writes_total"],
        "rows_stored":   total_rows,
        "tables":        list(executor.storage.tables.keys()),
        "replica_url":   REPLICA_URL,
    }


if __name__ == "__main__":
    uvicorn.run("node.api:app", host="0.0.0.0", port=PORT, reload=False)