def test_index_serves_frontend(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "匯率換算" in resp.text
    # 依第三方 API 使用條款，頁面上必須標示資料來源
    assert "Rates By Exchange Rate API" in resp.text


def test_static_assets_are_served(client):
    for path in ("/static/app.js", "/static/styles.css"):
        assert client.get(path).status_code == 200


def test_api_docs_still_available(client):
    assert client.get("/docs").status_code == 200
