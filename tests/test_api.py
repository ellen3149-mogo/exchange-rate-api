from tests.conftest import build_client


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_latest_rates(client):
    resp = client.get("/api/v1/rates/latest", params={"base": "usd"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"] == "USD"
    assert body["rates"]["TWD"] == "32.5"  # Decimal 以字串輸出，保留精度
    assert body["cached"] is False
    assert body["stale"] is False


def test_latest_rates_with_symbols(client):
    resp = client.get("/api/v1/rates/latest", params={"base": "USD", "symbols": "twd,jpy"})
    assert resp.status_code == 200
    assert set(resp.json()["rates"]) == {"TWD", "JPY"}


def test_unknown_symbol_returns_422(client):
    resp = client.get("/api/v1/rates/latest", params={"symbols": "TWD,XYZ"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unsupported_currency"


def test_invalid_base_format_returns_validation_error(client):
    resp = client.get("/api/v1/rates/latest", params={"base": "US1"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_second_request_uses_cache(client, upstream):
    client.get("/api/v1/rates/latest")
    resp = client.get("/api/v1/rates/latest")
    assert resp.json()["cached"] is True
    assert upstream.calls == 1


def test_convert(client):
    resp = client.post(
        "/api/v1/convert", json={"from_currency": "usd", "to_currency": "TWD", "amount": "100"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rate"] == "32.500000"
    assert body["result"] == "3250.0000"
    assert body["inverse_rate"] == "0.030769"


def test_convert_same_currency(client):
    resp = client.post(
        "/api/v1/convert", json={"from_currency": "USD", "to_currency": "USD", "amount": 12.5}
    )
    assert resp.json()["result"] == "12.5000"


def test_convert_rejects_non_positive_amount(client):
    resp = client.post(
        "/api/v1/convert", json={"from_currency": "USD", "to_currency": "TWD", "amount": 0}
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"][0]["field"] == "amount"


def test_convert_unsupported_target(client):
    resp = client.post(
        "/api/v1/convert", json={"from_currency": "USD", "to_currency": "ABC", "amount": 1}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unsupported_currency"


def test_convert_unsupported_base(client):
    resp = client.post(
        "/api/v1/convert", json={"from_currency": "ABC", "to_currency": "TWD", "amount": 1}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unsupported_currency"


def test_upstream_down_returns_503_with_retries(client, upstream):
    upstream.mode = "down"
    resp = client.get("/api/v1/rates/latest")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "upstream_unavailable"
    assert upstream.calls == 2  # max_retries=2


def test_malformed_upstream_returns_503(client, upstream):
    upstream.mode = "malformed"
    resp = client.get("/api/v1/rates/latest")
    assert resp.status_code == 503


def test_stale_data_served_when_upstream_fails(upstream):
    with build_client(upstream, cache_ttl_seconds=0) as c:
        assert c.get("/api/v1/rates/latest").status_code == 200
        upstream.mode = "down"
        resp = c.get("/api/v1/rates/latest")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True


def test_request_id_is_echoed(client):
    resp = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"


def test_error_includes_request_id(client):
    resp = client.get(
        "/api/v1/rates/latest", params={"symbols": "XYZ"}, headers={"X-Request-ID": "r1"}
    )
    assert resp.json()["error"]["request_id"] == "r1"
