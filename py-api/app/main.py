from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest

app = FastAPI(title="py-api")

# Prometheus metrics (explicit registry to keep things tidy)
REGISTRY = CollectorRegistry()
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["path", "method", "status"],
    registry=REGISTRY,
)
ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP 5xx",
    ["path", "method", "status"],
    registry=REGISTRY,
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        status = str(response.status_code)
    except Exception:
        # Count unhandled exceptions as 500s, then re-raise
        status = "500"
        ERROR_COUNT.labels(request.url.path, request.method, status).inc()
        REQUEST_COUNT.labels(request.url.path, request.method, status).inc()
        raise

    # Count every request
    REQUEST_COUNT.labels(request.url.path, request.method, status).inc()
    if status.startswith("5"):
        ERROR_COUNT.labels(request.url.path, request.method, status).inc()
    return response


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/work")
async def work(fail: bool = False):
    if fail:
        return JSONResponse(status_code=500, content={"error": "intentional failure"})
    # Simple deterministic compute to prove “work”
    value = sum(i * i for i in range(1, 101))  # 338350
    return {"result": value}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)