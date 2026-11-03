"""FastAPI 應用程式進入點。

使用 create_app() 工廠函式建立 app，測試時可注入假的 HTTP transport，
不必真的連到外部 API。
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging
from app.routers import rates
from app.schemas import HealthResponse
from app.services.rate_client import RateClient

logger = logging.getLogger("app.access")
STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 啟動時建立一個共用的 HTTP 連線池，關閉時釋放
        app.state.rate_client = RateClient(
            base_url=settings.rate_api_base_url,
            timeout=settings.rate_api_timeout_seconds,
            cache_ttl_seconds=settings.cache_ttl_seconds,
            max_retries=settings.rate_api_max_retries,
            transport=transport,
        )
        yield
        await app.state.rate_client.aclose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="即時匯率查詢與幣別換算微服務，部署於 Google Cloud Run。",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # 每個請求帶一個 request_id，錯誤回應與 log 都會附上，方便追查問題
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    register_exception_handlers(app)
    app.include_router(rates.router)

    # 前端：由同一個服務提供靜態網頁，與 API 同源，不需要另外部署或設定 CORS
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse, tags=["system"], summary="健康檢查")
    async def health():
        return HealthResponse(
            status="ok", version=settings.app_version, environment=settings.environment
        )

    return app


app = create_app()
