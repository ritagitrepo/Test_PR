import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.pinot_client import PinotClient, PinotError

TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
READ_ONLY_SQL = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "pinot"):
        app.state.pinot = PinotClient(Settings.from_env())
    yield
    await app.state.pinot.aclose()


app = FastAPI(title="Pinot Demo Service", lifespan=lifespan)


@app.exception_handler(PinotError)
async def pinot_error_handler(_: Request, exc: PinotError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


class QueryRequest(BaseModel):
    sql: str = Field(..., examples=["SELECT playerName, SUM(homeRuns) AS hr FROM baseballStats GROUP BY playerName ORDER BY hr DESC LIMIT 5"])


def pinot(request: Request) -> PinotClient:
    return request.app.state.pinot


def validate_table(table: str) -> str:
    if not TABLE_NAME.match(table):
        raise HTTPException(status_code=400, detail="Invalid table name")
    return table


@app.get("/health")
async def health(request: Request):
    status = await pinot(request).health()
    healthy = all(v == "OK" for v in status.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"healthy": healthy, "pinot": status})


@app.get("/tables")
async def list_tables(request: Request):
    return {"tables": await pinot(request).list_tables()}


@app.get("/tables/{table}/schema")
async def table_schema(table: str, request: Request):
    return await pinot(request).table_schema(validate_table(table))


@app.get("/tables/{table}/sample")
async def table_sample(table: str, request: Request, limit: int = Query(10, ge=1, le=100)):
    return await pinot(request).query(f"SELECT * FROM {validate_table(table)} LIMIT {limit}")


@app.get("/tables/{table}/count")
async def table_count(table: str, request: Request):
    result = await pinot(request).query(f"SELECT COUNT(*) AS cnt FROM {validate_table(table)}")
    return {"table": table, "count": result["rows"][0]["cnt"] if result["rows"] else 0}


@app.post("/query")
async def run_query(body: QueryRequest, request: Request):
    if not READ_ONLY_SQL.match(body.sql):
        raise HTTPException(status_code=400, detail="Only SELECT/WITH queries are allowed")
    return await pinot(request).query(body.sql)


@app.get("/demo/top-home-runs")
async def top_home_runs(request: Request, limit: int = Query(10, ge=1, le=100)):
    return await pinot(request).query(
        "SELECT playerName, SUM(homeRuns) AS totalHomeRuns FROM baseballStats "
        f"GROUP BY playerName ORDER BY totalHomeRuns DESC LIMIT {limit}"
    )
