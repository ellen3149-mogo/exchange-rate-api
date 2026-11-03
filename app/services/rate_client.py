"""第三方匯率 API 用戶端（含快取、重試、降級機制）。

設計重點：
1. 非同步 httpx.AsyncClient：等待外部 API 時不會阻塞其他請求。
2. 記憶體 TTL 快取：同一個 base 在 TTL 內只呼叫外部 API 一次。
3. 每個 base 一把鎖：避免快取過期瞬間大量請求同時打到外部 API（cache stampede）。
4. 重試 + 指數退避：處理暫時性網路錯誤。
5. 優雅降級：外部 API 掛掉時，若有舊資料則回傳並標記 stale=True。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.exceptions import UnsupportedCurrencyError, UpstreamServiceError

logger = logging.getLogger(__name__)
PROVIDER_NAME = "open.er-api.com"


@dataclass(frozen=True)
class RateTable:
    base: str
    rates: dict[str, Decimal]
    last_updated_utc: datetime
    next_update_utc: datetime
    cached: bool = False
    stale: bool = False


class RateClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        cache_ttl_seconds: int = 600,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_backoff_seconds: float = 0.3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )
        self._ttl = cache_ttl_seconds
        self._max_retries = max_retries
        self._backoff = retry_backoff_seconds
        self._cache: dict[str, tuple[float, RateTable]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    def _fresh(self, base: str) -> RateTable | None:
        entry = self._cache.get(base)
        if entry and time.monotonic() - entry[0] < self._ttl:
            return replace(entry[1], cached=True)
        return None

    async def get_rates(self, base: str) -> RateTable:
        base = base.upper()
        if table := self._fresh(base):
            return table

        lock = self._locks.setdefault(base, asyncio.Lock())
        async with lock:
            # 拿到鎖後再檢查一次：可能已被其他請求更新
            if table := self._fresh(base):
                return table
            try:
                table = await self._fetch(base)
            except UpstreamServiceError:
                stale = self._cache.get(base)
                if stale:
                    logger.warning("匯率 API 無法使用，回傳舊資料 base=%s", base)
                    return replace(stale[1], cached=True, stale=True)
                raise
            self._cache[base] = (time.monotonic(), table)
            return table

    async def _fetch(self, base: str) -> RateTable:
        data = await self._request_with_retry(f"/latest/{base}")

        if data.get("result") != "success":
            error_type = data.get("error-type", "unknown")
            if error_type == "unsupported-code":
                raise UnsupportedCurrencyError(f"不支援的幣別：{base}")
            raise UpstreamServiceError(f"匯率資料源回應錯誤：{error_type}")

        try:
            rates = {code: Decimal(str(v)) for code, v in data["rates"].items()}
            return RateTable(
                base=data["base_code"],
                rates=rates,
                last_updated_utc=datetime.fromtimestamp(int(data["time_last_update_unix"]), tz=UTC),
                next_update_utc=datetime.fromtimestamp(int(data["time_next_update_unix"]), tz=UTC),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.error("匯率資料格式不正確：%r", exc)
            raise UpstreamServiceError("匯率資料源回應格式異常") from exc

    async def _request_with_retry(self, path: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.get(path)
                # 4xx 代表請求本身有問題（例如幣別不存在），不重試，交由上層解析錯誤內容
                if resp.status_code >= 500:
                    resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning("匯率 API 第 %d/%d 次失敗：%s", attempt, self._max_retries, exc)
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
        # 詳細錯誤只寫入 log，不回傳給呼叫端，避免洩漏內部資訊
        logger.error("匯率 API 重試 %d 次仍失敗：%r", self._max_retries, last_error)
        raise UpstreamServiceError("匯率資料源暫時無法使用，請稍後再試")
