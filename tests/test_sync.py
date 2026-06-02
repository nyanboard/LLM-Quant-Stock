"""
data/sync.py 和 data/scheduler.py 的单元测试

测试覆盖范围：
1. MetricsSyncer:
   - 缓存命中时跳过同步（sync_if_stale 返回缓存数据）
   - 缓存过期时触发同步（调用 datasource.get_stock_metrics）
   - 数据源失败时重试（最多 max_retries 次）
   - 全部重试失败返回 None
   - 实时行情数据合并到慢数据中
2. DataScheduler:
   - 完整每日流程（获取股票列表 → 指标同步）
   - 股票列表获取失败时不继续后续步骤
   - is_data_stale() 判断逻辑

Mock 策略：
- 使用 unittest.mock 替换 DataSource 的实际调用
- DataCache 使用临时文件的 SQLite 数据库，测试完自动清理
- 不依赖外部 API，测试可在离线环境运行
"""
import time
from unittest.mock import MagicMock

import pandas as pd
import pytest

from data.cache import DataCache
from data.scheduler import DataScheduler
from data.sync import MetricsSyncer


# ────────────────────────────────────────────
# 测试 fixtures
# ────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path):
    """创建使用临时文件的 DataCache 实例

    每个测试函数获得独立的 cache 实例，测试结束后文件自动清理。
    自动初始化 stock_metrics 宽表。
    """
    db_path = str(tmp_path / "test_stock_data.db")
    c = DataCache(db_path)
    c.init_metrics_table()
    return c


@pytest.fixture
def mock_datasource():
    """创建 mock 数据源，默认返回包含 3 只股票的指标 DataFrame"""
    ds = MagicMock()
    ds.get_stock_metrics.return_value = pd.DataFrame([
        {"symbol": "600519", "name": "贵州茅台", "market_cap": 20000, "pe": 35, "pb": 10, "roe": 30},
        {"symbol": "000858", "name": "五粮液", "market_cap": 5000, "pe": 25, "pb": 8, "roe": 25},
        {"symbol": "000001", "name": "平安银行", "market_cap": 3000, "pe": 6, "pb": 0.6, "roe": 12},
    ])
    ds.get_stock_list.return_value = ["600519", "000858", "000001"]
    ds.get_realtime_quotes.return_value = pd.DataFrame([
        {"symbol": "600519", "is_st": False, "is_suspended": False, "price": 1800.0,
         "is_limit_up": False, "is_limit_down": False, "turnover_rate": 0.5, "avg_amount": 50000},
        {"symbol": "000858", "is_st": False, "is_suspended": False, "price": 150.0,
         "is_limit_up": False, "is_limit_down": False, "turnover_rate": 0.8, "avg_amount": 30000},
        {"symbol": "000001", "is_st": False, "is_suspended": False, "price": 12.0,
         "is_limit_up": False, "is_limit_down": False, "turnover_rate": 1.2, "avg_amount": 20000},
    ])
    return ds


# ────────────────────────────────────────────
# MetricsSyncer 测试
# ────────────────────────────────────────────

class TestMetricsSyncer:
    """MetricsSyncer 单元测试"""

    def test_cache_hit_returns_cached_data(self, cache, mock_datasource):
        """缓存未过期时，sync_if_stale 应返回缓存数据，不调用数据源"""
        df = pd.DataFrame([{
            "symbol": "600519", "name": "贵州茅台", "industry": None,
            "list_date": None, "market_cap": 20000, "pe": 35, "pb": 10,
            "roe": 30, "debt_ratio": None, "revenue": None,
            "operating_cashflow": None, "synced_at": time.time(),
        }])
        cache.upsert_metrics(df)

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        result = syncer.sync_if_stale(["600519"])

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "600519"
        mock_datasource.get_stock_metrics.assert_not_called()

    def test_cache_expired_triggers_sync(self, cache, mock_datasource):
        """缓存过期时，sync_if_stale 应调用数据源重新获取"""
        df = pd.DataFrame([{
            "symbol": "600519", "name": "贵州茅台", "industry": None,
            "list_date": None, "market_cap": 20000, "pe": 35, "pb": 10,
            "roe": 30, "debt_ratio": None, "revenue": None,
            "operating_cashflow": None, "synced_at": time.time() - 172800,
        }])
        cache.upsert_metrics(df)

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        result = syncer.sync_if_stale(["600519"])

        mock_datasource.get_stock_metrics.assert_called_once()
        assert result is not None
        assert len(result) == 3

    def test_no_cache_triggers_sync(self, cache, mock_datasource):
        """没有任何缓存时，应从数据源获取"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        result = syncer.sync_if_stale(["600519", "000858"])

        mock_datasource.get_stock_metrics.assert_called_once()
        assert result is not None
        assert len(result) == 3

    def test_retry_on_failure(self, cache):
        """数据源失败时，应重试 max_retries 次"""
        ds = MagicMock()
        ds.get_stock_metrics.side_effect = Exception("API 限流")

        syncer = MetricsSyncer(datasource=ds, cache=cache, max_retries=3, request_interval=0.01)
        result = syncer.sync_if_stale(["600519"])

        assert result is None
        assert ds.get_stock_metrics.call_count == 3

    def test_partial_recovery_on_retry(self, cache):
        """第一次失败、第二次成功时，应返回第二次的数据"""
        ds = MagicMock()
        ds.get_stock_metrics.side_effect = [
            Exception("临时错误"),
            pd.DataFrame([{"symbol": "600519", "name": "贵州茅台", "pe": 35}]),
        ]

        syncer = MetricsSyncer(datasource=ds, cache=cache, max_retries=3, request_interval=0.01)
        result = syncer.sync_if_stale(["600519"])

        assert result is not None
        assert ds.get_stock_metrics.call_count == 2

    def test_realtime_data_merged(self, cache, mock_datasource):
        """实时行情数据应合并到慢数据中"""
        syncer = MetricsSyncer(
            datasource=mock_datasource, cache=cache,
            secondary_datasource=mock_datasource, request_interval=0.01,
        )
        result = syncer.sync_if_stale(["600519", "000858", "000001"])

        assert result is not None
        # 检查实时字段存在
        assert "is_st" in result.columns
        assert "price" in result.columns
        assert "turnover_rate" in result.columns

    def test_realtime_failure_does_not_block(self, cache, mock_datasource):
        """实时数据源失败时不应阻塞慢数据同步"""
        ds_fail = MagicMock()
        ds_fail.get_stock_metrics.return_value = pd.DataFrame([
            {"symbol": "600519", "name": "贵州茅台", "pe": 35},
        ])
        ds_fail.get_realtime_quotes.side_effect = Exception("实时行情接口异常")

        syncer = MetricsSyncer(
            datasource=ds_fail, cache=cache,
            secondary_datasource=ds_fail, request_interval=0.01,
        )
        result = syncer.sync_if_stale(["600519"])

        # 慢数据应该正常返回
        assert result is not None
        assert len(result) == 1


# ────────────────────────────────────────────
# DataScheduler 测试
# ────────────────────────────────────────────

class TestDataScheduler:
    """DataScheduler 单元测试"""

    def test_full_daily_flow(self, cache, mock_datasource):
        """完整的每日流程：获取股票列表 → 指标同步"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        result = scheduler.run_daily("hs300")

        assert result is not None
        assert result["universe"] == "hs300"
        assert result["synced_count"] == 3

    def test_stock_list_failure_stops_flow(self, cache, mock_datasource):
        """股票列表获取失败时，不应继续后续步骤"""
        mock_datasource.get_stock_list.side_effect = Exception("网络错误")

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        result = scheduler.run_daily("hs300")

        assert result is None

    def test_is_data_stale_no_data(self, cache, mock_datasource):
        """从未执行过同步时，is_data_stale 应返回 True"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        assert scheduler.is_data_stale() is True

    def test_is_data_stale_fresh_data(self, cache, mock_datasource):
        """刚执行完同步时，is_data_stale 应返回 False"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        scheduler.run_daily("hs300")
        assert scheduler.is_data_stale() is False

    def test_is_data_stale_expired_data(self, cache, mock_datasource):
        """数据过期时，is_data_stale 应返回 True"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        scheduler.run_daily("hs300")
        # TTL=0 强制过期
        assert scheduler.is_data_stale(ttl=0) is True
