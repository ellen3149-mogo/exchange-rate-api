"""測試共用設定：以 httpx.MockTransport 模擬第三方 API，測試不需要網路、結果穩定可重現。"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SAMPLE_USD = {
    "result": "success",
    "base_code": "USD",
    "time_last_update_unix": 1793664001,
    "time_next_update_unix": 1793750401,
    "rates": {"USD": 1, "TWD": 32.5, "JPY": 150.25, "EUR": 0.92},
}


class FakeUpstream:
    """可控制行為的假匯率 API：記錄呼叫次數、可切換成故障模式。"""

    def __init__(self) -> None:
        self.calls = 0
        self.mode = "ok"  # ok | down | unsupported | malformed

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.mode == "down":
            return httpx.Response(503, json={"result": "error"})
        if self.mode == "malformed":
            return httpx.Response(200, json={"result": "success", "rates": "oops"})
        base = request.url.path.rsplit("/", 1)[-1]
        if self.mode == "unsupported" or base not in ("USD", "TWD"):
            return httpx.Response(404, json={"result": "error", "error-type": "unsupported-code"})
        if base == "TWD":
            data = {**SAMPLE_USD, "base_code": "TWD", "rates": {"TWD": 1, "USD": 0.030769}}
            return httpx.Response(200, json=data)
        return httpx.Response(200, json=SAMPLE_USD)


def build_client(upstream: FakeUpstream, **overrides) -> TestClient:
    settings = Settings(
        rate_api_base_url="https://fake.test/v6",
        rate_api_max_retries=2,
        log_level="WARNING",
        **overrides,
    )
    app = create_app(settings, transport=httpx.MockTransport(upstream.handler))
    return TestClient(app)


@pytest.fixture
def upstream() -> FakeUpstream:
    return FakeUpstream()


@pytest.fixture
def client(upstream):
    with build_client(upstream) as c:
        yield c
