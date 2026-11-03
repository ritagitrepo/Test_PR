# Pinot Demo Service

Small FastAPI service that shows how to access [Apache Pinot](https://pinot.apache.org/): it talks to the Pinot **broker** (SQL queries) and **controller** (table metadata) over their REST APIs.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Broker + controller health |
| GET | `/tables` | List Pinot tables |
| GET | `/tables/{table}/schema` | Table schema |
| GET | `/tables/{table}/sample?limit=10` | First N rows |
| GET | `/tables/{table}/count` | Row count |
| POST | `/query` | Run a read-only SQL query: `{"sql": "SELECT ..."}` |
| GET | `/demo/top-home-runs?limit=10` | Example aggregation on the quickstart `baseballStats` table |

Interactive docs: `http://localhost:8000/docs`.

## Configuration

| Env var | Default | Description |
| --- | --- | --- |
| `PINOT_BROKER_URL` | `http://localhost:8099` | Broker base URL |
| `PINOT_CONTROLLER_URL` | `http://localhost:9000` | Controller base URL |
| `PINOT_AUTH_TOKEN` | _(unset)_ | Sent as-is in the `Authorization` header, e.g. `Basic <b64>` or `Bearer <token>` |
| `PINOT_TIMEOUT_SECONDS` | `10` | HTTP timeout |

## Run the demo (Pinot quickstart + service)

```bash
docker compose up --build
# wait until Pinot is healthy (~1-2 min), then:
curl localhost:8000/health
curl localhost:8000/tables
curl 'localhost:8000/demo/top-home-runs?limit=5'
curl -X POST localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT teamID, COUNT(*) AS players FROM baseballStats GROUP BY teamID ORDER BY players DESC LIMIT 5"}'
```

## Run locally against an existing Pinot

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
PINOT_BROKER_URL=http://my-broker:8099 PINOT_CONTROLLER_URL=http://my-controller:9000 \
  uvicorn app.main:app --reload
pytest
```
