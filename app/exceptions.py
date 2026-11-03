"""自訂例外與統一錯誤格式。

所有錯誤都回傳相同結構，前端與呼叫端只需處理一種格式：
{"error": {"code": "...", "message": "...", "request_id": "..."}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedCurrencyError(AppError):
    status_code = 422
    code = "unsupported_currency"


class UpstreamServiceError(AppError):
    """第三方匯率 API 無法使用（逾時、5xx、格式錯誤）。"""

    status_code = 503
    code = "upstream_unavailable"


def _error_body(request: Request, code: str, message: str, details=None) -> dict:
    body = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("AppError %s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code, content=_error_body(request, exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(request, "validation_error", "請求參數格式不正確", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, "http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        # 未預期錯誤：完整堆疊寫入 log，但不把內部細節回傳給呼叫端
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500, content=_error_body(request, "internal_error", "伺服器發生未預期錯誤")
        )
