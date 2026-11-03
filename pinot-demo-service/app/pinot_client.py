from typing import Any

import httpx

from app.config import Settings


class PinotError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class PinotClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        headers = {"Content-Type": "application/json"}
        if settings.auth_token:
            headers["Authorization"] = settings.auth_token
        self._broker = httpx.AsyncClient(
            base_url=settings.broker_url, headers=headers,
            timeout=settings.timeout_seconds, transport=transport,
        )
        self._controller = httpx.AsyncClient(
            base_url=settings.controller_url, headers=headers,
            timeout=settings.timeout_seconds, transport=transport,
        )

    async def aclose(self) -> None:
        await self._broker.aclose()
        await self._controller.aclose()

    async def _request(self, client: httpx.AsyncClient, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise PinotError(f"Cannot reach Pinot at {client.base_url}: {exc}", 503) from exc
        if response.status_code == 404:
            raise PinotError(f"Not found: {path}", 404)
        if response.is_error:
            raise PinotError(f"Pinot returned {response.status_code}: {response.text[:500]}")
        return response

    async def health(self) -> dict[str, str]:
        result = {}
        for name, client in (("broker", self._broker), ("controller", self._controller)):
            try:
                await self._request(client, "GET", "/health")
                result[name] = "OK"
            except PinotError as exc:
                result[name] = str(exc)
        return result

    async def list_tables(self) -> list[str]:
        response = await self._request(self._controller, "GET", "/tables")
        return response.json().get("tables", [])

    async def table_schema(self, table: str) -> dict[str, Any]:
        response = await self._request(self._controller, "GET", f"/tables/{table}/schema")
        return response.json()

    async def query(self, sql: str) -> dict[str, Any]:
        response = await self._request(self._broker, "POST", "/query/sql", json={"sql": sql})
        body = response.json()
        exceptions = body.get("exceptions") or []
        if exceptions:
            raise PinotError(f"Query failed: {exceptions[0].get('message', exceptions)}", 400)
        table = body.get("resultTable", {})
        schema = table.get("dataSchema", {})
        columns = schema.get("columnNames", [])
        return {
            "columns": columns,
            "columnTypes": schema.get("columnDataTypes", []),
            "rows": [dict(zip(columns, row)) for row in table.get("rows", [])],
            "stats": {
                "timeUsedMs": body.get("timeUsedMs"),
                "numDocsScanned": body.get("numDocsScanned"),
                "totalDocs": body.get("totalDocs"),
            },
        }
