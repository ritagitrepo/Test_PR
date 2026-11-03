import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.pinot_client import PinotClient

SETTINGS = Settings(broker_url="http://broker", controller_url="http://controller", auth_token="Bearer t", timeout_seconds=1)


def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer t"
    if request.url.path == "/health":
        return httpx.Response(200, text="OK")
    if request.url.host == "controller" and request.url.path == "/tables":
        return httpx.Response(200, json={"tables": ["baseballStats"]})
    if request.url.path == "/tables/baseballStats/schema":
        return httpx.Response(200, json={"schemaName": "baseballStats"})
    if request.url.path == "/query/sql":
        sql = json.loads(request.content)["sql"]
        if "missing" in sql:
            return httpx.Response(200, json={"exceptions": [{"errorCode": 190, "message": "TableDoesNotExistError"}]})
        return httpx.Response(200, json={
            "resultTable": {
                "dataSchema": {"columnNames": ["playerName", "cnt"], "columnDataTypes": ["STRING", "LONG"]},
                "rows": [["Babe Ruth", 714]],
            },
            "exceptions": [], "timeUsedMs": 3, "numDocsScanned": 10, "totalDocs": 10,
        })
    return httpx.Response(404)


@pytest.fixture
def client():
    app.state.pinot = PinotClient(SETTINGS, transport=httpx.MockTransport(handler))
    with TestClient(app) as c:
        yield c
    del app.state.pinot


def test_health(client):
    assert client.get("/health").json() == {"healthy": True, "pinot": {"broker": "OK", "controller": "OK"}}


def test_tables_and_schema(client):
    assert client.get("/tables").json() == {"tables": ["baseballStats"]}
    assert client.get("/tables/baseballStats/schema").json()["schemaName"] == "baseballStats"


def test_query_maps_rows(client):
    body = client.post("/query", json={"sql": "SELECT playerName, cnt FROM baseballStats"}).json()
    assert body["rows"] == [{"playerName": "Babe Ruth", "cnt": 714}]
    assert body["stats"]["timeUsedMs"] == 3


def test_count(client):
    assert client.get("/tables/baseballStats/count").json() == {"table": "baseballStats", "count": 714}


def test_rejects_non_select(client):
    assert client.post("/query", json={"sql": "DELETE FROM baseballStats"}).status_code == 400


def test_rejects_bad_table_name(client):
    assert client.get("/tables/x;drop/sample").status_code == 400


def test_pinot_query_error_surfaces(client):
    r = client.post("/query", json={"sql": "SELECT * FROM missing"})
    assert r.status_code == 400 and "TableDoesNotExistError" in r.json()["detail"]
