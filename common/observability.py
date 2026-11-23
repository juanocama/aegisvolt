"""Small, dependency-free JSON request logging for service containers."""

import contextvars
import json
import logging
import os
import re
import sys
import time
import uuid

from fastapi import FastAPI, Request

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "aegisvolt_correlation_id", default=""
)
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
logger = logging.getLogger("aegisvolt.request")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def current_correlation_id() -> str:
    return _correlation_id.get()


def install_request_logging(app: FastAPI, service: str) -> None:
    @app.middleware("http")
    async def request_log(request: Request, call_next):
        incoming_correlation_id = request.headers.get("x-correlation-id", "")
        correlation_id = (
            incoming_correlation_id
            if _CORRELATION_ID_PATTERN.fullmatch(incoming_correlation_id)
            else str(uuid.uuid4())
        )
        token = _correlation_id.set(correlation_id)
        started = time.perf_counter()
        status_code = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            route = request.scope.get("route")
            route_template = getattr(route, "path", None)
            logger.info(json.dumps({
                "timestamp": time.time(),
                "environment": os.getenv("ENVIRONMENT", "dev"),
                "service": service,
                "correlation_id": correlation_id,
                "method": request.method,
                # Middleware may run before routing. Never fall back to a raw URL
                # path because it can contain customer/resource identifiers.
                "path": route_template or "<unmatched>",
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }, separators=(",", ":")))
            _correlation_id.reset(token)
