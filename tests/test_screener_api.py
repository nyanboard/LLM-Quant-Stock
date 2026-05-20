"""
api/routers/screener.py 的测试

使用 FastAPI TestClient 验证 4 个端点的请求/响应格式。
DataCache 使用临时 SQLite，不依赖外部 API。
"""
import time

import pytest
from fastapi.testclient import TestClient

from data.cache import DataCache


@pytest.fixture
def cache(tmp_path):
    """创建使用临时文件的 DataCache，初始化所有预筛相关表"""
    db_path = str(tmp_path / "test_api.db")
    c = DataCache(db_path)
    c.init_metrics_table()
    c.init_pool_table()
    c.init_screening_tables()
    return c


@pytest.fixture
def client(cache):
    """创建 FastAPI TestClient，注入临时 DataCache"""
    from api import app
    from api.routers import screener

    screener.set_cache(cache)
    return TestClient(app)


def _insert_screening(cache, universe="hs300", total=10, passed=6, excluded=4):
    """辅助方法：插入一条预筛结果记录"""
    pool_id = cache.save_stock_pool(universe, ["600519"] * total)
    passed_stocks = [
        {"symbol": f"6000{i}", "name": f"测试股{i}", "passed": 1,
         "market_cap": 100 + i, "pe": 20 + i, "pb": 2 + i, "roe": 10 + i, "price": 10 + i}
        for i in range(passed)
    ]
    excluded_stocks = [
        {"symbol": f"0000{i}", "name": f"淘汰股{i}", "passed": 0,
         "reasons": ["ST/*ST"], "market_cap": 10, "pe": -5, "pb": 0.5, "roe": 1, "price": 1.5}
        for i in range(excluded)
    ]
    result = {
        "universe": universe,
        "passed": passed_stocks,
        "excluded": excluded_stocks,
        "stats": {
            "total": total,
            "passed_count": passed,
            "excluded_count": excluded,
            "dimension_breakdown": {"ST": excluded},
        },
    }
    return cache.save_screening_result(result, pool_id=pool_id)


# ── POST /run ──

class TestRunScreening:
    def test_run_returns_running_status(self, client):
        resp = client.post("/api/v1/screener/run", json={"universe": "hs300"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["universe"] == "hs300"
        assert data["screening_id"] is None

    def test_run_with_default_universe(self, client):
        resp = client.post("/api/v1/screener/run", json={})
        assert resp.status_code == 200
        assert resp.json()["universe"] == "hs300"


# ── GET /result ──

class TestGetResult:
    def test_get_latest_result(self, client, cache):
        _insert_screening(cache, universe="hs300", total=10, passed=6, excluded=4)

        resp = client.get("/api/v1/screener/result")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["universe"] == "hs300"
        assert len(data["passed"]) == 6
        assert len(data["excluded"]) == 4
        assert data["stats"]["total"] == 10
        assert data["stats"]["passed_count"] == 6
        assert data["stats"]["excluded_count"] == 4

    def test_get_result_by_id(self, client, cache):
        sid = _insert_screening(cache, universe="zz500", total=5, passed=3, excluded=2)

        resp = client.get("/api/v1/screener/result", params={"screening_id": sid})
        assert resp.status_code == 200
        data = resp.json()
        assert data["screening_id"] == sid
        assert data["universe"] == "zz500"
        assert len(data["passed"]) == 3

    def test_get_result_not_found(self, client, cache):
        resp = client.get("/api/v1/screener/result", params={"screening_id": 9999})
        assert resp.status_code == 404

    def test_get_result_no_data(self, client, cache):
        resp = client.get("/api/v1/screener/result")
        assert resp.status_code == 404

    def test_result_stock_item_fields(self, client, cache):
        _insert_screening(cache, universe="hs300", total=3, passed=1, excluded=2)

        resp = client.get("/api/v1/screener/result")
        data = resp.json()
        stock = data["passed"][0]
        assert "symbol" in stock
        assert "name" in stock
        assert "passed" in stock
        assert stock["passed"] == 1

        excluded_stock = data["excluded"][0]
        assert "exclusion_reasons" in excluded_stock
        assert isinstance(excluded_stock["exclusion_reasons"], list)


# ── GET /stats ──

class TestGetStats:
    def test_get_stats(self, client, cache):
        _insert_screening(cache, universe="hs300", total=10, passed=6, excluded=4)

        resp = client.get("/api/v1/screener/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert data["passed_count"] == 6
        assert data["excluded_count"] == 4
        assert isinstance(data["dimension_breakdown"], dict)

    def test_get_stats_no_data(self, client, cache):
        resp = client.get("/api/v1/screener/stats")
        assert resp.status_code == 404


# ── GET /history ──

class TestGetHistory:
    def test_get_history(self, client, cache):
        _insert_screening(cache, universe="hs300")
        _insert_screening(cache, universe="zz500")

        resp = client.get("/api/v1/screener/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["universe"] == "zz500"  # 最新在前
        assert data[1]["universe"] == "hs300"

    def test_get_history_with_limit(self, client, cache):
        for i in range(5):
            _insert_screening(cache, universe="hs300")

        resp = client.get("/api/v1/screener/history", params={"limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_history_empty(self, client, cache):
        resp = client.get("/api/v1/screener/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_item_fields(self, client, cache):
        _insert_screening(cache, universe="hs300", total=8, passed=5, excluded=3)

        resp = client.get("/api/v1/screener/history")
        item = resp.json()[0]
        assert "screening_id" in item
        assert "universe" in item
        assert "total_count" in item
        assert "passed_count" in item
        assert "excluded_count" in item
        assert "created_at" in item
