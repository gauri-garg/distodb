import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from node.executor import Executor
import os

NODE_ID = os.environ.get("NODE_ID", "node1")

app = FastAPI()
executor = Executor()
metrics = {"queries_total": 0, "writes_total": 0}


class QueryRequest(BaseModel):
    sql: str


@app.post("/query")
def query(req: QueryRequest):
    result = executor.run(req.sql)
    metrics["queries_total"] += 1
    sql_lower = req.sql.strip().lower()
    if any(sql_lower.startswith(w) for w in ("insert", "update", "delete", "create")):
        metrics["writes_total"] += 1
    return result


@app.get("/health")
def health():
    return {"status": "ok", "node_id": NODE_ID}


@app.get("/metrics")
def get_metrics():
    total_rows = sum(
        len(t["rows"]) for t in executor.storage.tables.values()
    )
    return {
        "node_id": NODE_ID,
        "queries_total": metrics["queries_total"],
        "writes_total": metrics["writes_total"],
        "rows_stored": total_rows,
        "tables": list(executor.storage.tables.keys()),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("node.api:app", host="0.0.0.0", port=port, reload=False)
