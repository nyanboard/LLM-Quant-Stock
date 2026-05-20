"""
data/sync.py 和 data/scheduler.py 的单元测试

测试覆盖范围：
1. MetricsSyncer:
   - 缓存命中时跳过同步（sync_if_stale 返回缓存数据）
   - 缓存过期时触发同步（调用 datasource.get_stock_metrics）
   - 数据源失败时重试（最多 max_retries 次）
   - 全部重试失败返回 None
2. DataScheduler:
   - 完整每日流程（股票池 → 指标 → 预筛）
   - 股票池同步失败时不继续后续步骤
   - 未配置预筛器时只执行同步
   - is_data_stale() 判断逻辑

Mock 策略：
- 使用 unittest.mock 替换 DataSource 和 Screener 的实际调用
- DataCache 使用临时的内存 SQLite 数据库（:memory:），测试完自动销毁
- 不依赖外部 API，测试可在离线环境运行
"""
import time
from unittest.mock import MagicMock, patch

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
    自动初始化所有需要的表（metrics、pool、screening）。
    """
    db_path = str(tmp_path / "test_stock_data.db")
    c = DataCache(db_path)
    c.init_metrics_table()
    c.init_pool_table()
    c.init_screening_tables()
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
    return ds


@pytest.fixture
def mock_screener():
    """创建 mock 预筛器，默认返回 2 通过 + 1 过滤的结果"""
    screener = MagicMock()
    screener.screen.return_value = {
        "passed": [
            {"symbol": "600519", "name": "贵州茅台", "pe": 35, "pb": 10},
            {"symbol": "000858", "name": "五粮液", "pe": 25, "pb": 8},
        ],
        "excluded": [
            {"symbol": "000001", "name": "平安银行", "reasons": ["市值过低"], "pe": 6, "pb": 0.6},
        ],
        "stats": {
            "total": 3,
            "passed_count": 2,
            "excluded_count": 1,
            "dimension_breakdown": {"市值": 1},
        },
    }
    return screener


# ────────────────────────────────────────────
# MetricsSyncer 测试
# ────────────────────────────────────────────

class TestMetricsSyncer:
    """MetricsSyncer 单元测试"""

    def test_cache_hit_returns_cached_data(self, cache, mock_datasource):
        """缓存未过期时，sync_if_stale 应返回缓存数据，不调用数据源"""
        # 先手动写入缓存数据
        df = pd.DataFrame([{
            "symbol": "600519", "name": "贵州茅台", "industry": None,
            "list_date": None, "market_cap": 20000, "pe": 35, "pb": 10,
            "roe": 30, "debt_ratio": None, "revenue": None,
            "operating_cashflow": None, "synced_at": time.time(),
        }])
        cache.upsert_metrics(df)

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        result = syncer.sync_if_stale(["600519"])

        # 应该返回缓存的数据
        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "600519"
        # 数据源不应被调用（缓存命中）
        mock_datasource.get_stock_metrics.assert_not_called()

    def test_cache_expired_triggers_sync(self, cache, mock_datasource):
        """缓存过期时，sync_if_stale 应调用数据源重新获取"""
        # 写入过期的缓存数据（synced_at 设为 2 天前）
        df = pd.DataFrame([{
            "symbol": "600519", "name": "贵州茅台", "industry": None,
            "list_date": None, "market_cap": 20000, "pe": 35, "pb": 10,
            "roe": 30, "debt_ratio": None, "revenue": None,
            "operating_cashflow": None, "synced_at": time.time() - 172800,  # 2天前
        }])
        cache.upsert_metrics(df)

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        result = syncer.sync_if_stale(["600519"])

        # 数据源应该被调用
        mock_datasource.get_stock_metrics.assert_called_once()
        # 返回的数据来自数据源（3 只股票）
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

        # 应该返回 None（全部失败）
        assert result is None
        # 应该调用了 3 次（max_retries）
        assert ds.get_stock_metrics.call_count == 3

    def test_partial_recovery_on_retry(self, cache):
        """第一次失败、第二次成功时，应返回第二次的数据"""
        ds = MagicMock()
        # 第一次失败，第二次成功
        ds.get_stock_metrics.side_effect = [
            Exception("临时错误"),
            pd.DataFrame([{"symbol": "600519", "name": "贵州茅台", "pe": 35}]),
        ]

        syncer = MetricsSyncer(datasource=ds, cache=cache, max_retries=3, request_interval=0.01)
        result = syncer.sync_if_stale(["600519"])

        # 应该在第二次重试时成功
        assert result is not None
        assert ds.get_stock_metrics.call_count == 2


# ────────────────────────────────────────────
# DataScheduler 测试
# ────────────────────────────────────────────

class TestDataScheduler:
    """DataScheduler 单元测试"""

    def test_full_daily_flow(self, cache, mock_datasource, mock_screener):
        """完整的每日流程：股票池 → 指标 → 预筛"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
            screener=mock_screener,
        )
        result = scheduler.run_daily("hs300")

        # 应该返回完整结果
        assert result is not None
        assert result["screening_id"] is not None
        assert result["pool_id"] is not None
        assert result["passed_count"] == 2
        assert result["excluded_count"] == 1
        assert result["total_count"] == 3

        # stock_pools 表应有 1 条记录
        pool = cache.get_latest_pool("hs300")
        assert pool is not None
        assert len(pool["symbols"]) == 3

        # screening_results 表应有 1 条记录
        screening = cache.get_latest_screening()
        assert screening is not None
        assert screening["passed_count"] == 2
        assert len(screening["stocks"]) == 3  # 2 passed + 1 excluded

    def test_no_screener_only_syncs(self, cache, mock_datasource):
        """未配置预筛器时，只执行同步步骤"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
            screener=None,
        )
        result = scheduler.run_daily("hs300")

        # 应返回结果但 screening_id 为 None
        assert result is not None
        assert result["screening_id"] is None
        assert result["pool_id"] is not None
        # 股票池应该已同步
        pool = cache.get_latest_pool("hs300")
        assert pool is not None

    def test_stock_pool_failure_stops_flow(self, cache, mock_datasource, mock_screener):
        """股票池同步失败时，不应继续后续步骤"""
        mock_datasource.get_stock_list.side_effect = Exception("网络错误")

        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
            screener=mock_screener,
        )
        result = scheduler.run_daily("hs300")

        # 应该返回 None（流程中断）
        assert result is None
        # 预筛器不应被调用
        mock_screener.screen.assert_not_called()

    def test_is_data_stale_no_data(self, cache, mock_datasource):
        """从未执行过预筛时，is_data_stale 应返回 True"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
        )
        assert scheduler.is_data_stale() is True

    def test_is_data_stale_fresh_data(self, cache, mock_datasource, mock_screener):
        """刚执行完预筛时，is_data_stale 应返回 False"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
            screener=mock_screener,
        )
        scheduler.run_daily("hs300")
        assert scheduler.is_data_stale() is False

    def test_is_data_stale_expired_data(self, cache, mock_datasource, mock_screener):
        """预筛结果过期时，is_data_stale 应返回 True"""
        syncer = MetricsSyncer(datasource=mock_datasource, cache=cache, request_interval=0.01)
        scheduler = DataScheduler(
            datasource=mock_datasource,
            cache=cache,
            syncer=syncer,
            screener=mock_screener,
        )
        scheduler.run_daily("hs300")
        # 用 TTL=0 检查，相当于强制过期
        assert scheduler.is_data_stale(ttl=0) is True
