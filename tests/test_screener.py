"""
quant/screener.py 的单元测试

测试覆盖范围：
1. 各维度过滤逻辑的正确性（8 个维度）
2. 边界值测试（刚好在阈值上/下）
3. 全通过 / 全失败场景
4. 统计输出（dimension_breakdown）
5. YAML 配置缺失时的行为

Mock 策略：
- DataCache 使用临时 SQLite，手动写入 stock_metrics 数据
- 不依赖外部 API，纯本地测试
- realtime_data 通过参数直接传入
"""
import time

import pandas as pd
import pytest

from data.cache import DataCache
from quant.screener import StockScreener


# ────────────────────────────────────────────
# 测试 fixtures
# ────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path):
    """创建使用临时文件的 DataCache，并初始化 metrics 表"""
    db_path = str(tmp_path / "test_screener.db")
    c = DataCache(db_path)
    c.init_metrics_table()
    return c


@pytest.fixture
def screener(cache):
    """创建使用项目实际 quant_rules.yaml 的预筛器"""
    return StockScreener(cache=cache, rules_path="config/quant_rules.yaml")


def _write_metrics(cache, stocks):
    """辅助方法：向 stock_metrics 表写入测试数据

    Args:
        cache: DataCache 实例
        stocks: 字典列表，每个字典代表一只股票的指标数据
    """
    df = pd.DataFrame(stocks)
    df["synced_at"] = time.time()
    cache.upsert_metrics(df)


# ────────────────────────────────────────────
# 基本场景测试
# ────────────────────────────────────────────

class TestScreenerBasic:
    """基本场景测试：全通过、全失败、混合"""

    def test_all_pass(self, screener, cache):
        """所有股票都满足条件时，全部通过"""
        _write_metrics(cache, [
            {
                "symbol": "600519", "name": "贵州茅台", "market_cap": 2000,
                "pe": 35, "pb": 10, "roe": 30, "debt_ratio": 30,
                "revenue": 1200, "operating_cashflow": 600,
            },
            {
                "symbol": "000858", "name": "五粮液", "market_cap": 500,
                "pe": 25, "pb": 8, "roe": 25, "debt_ratio": 40,
                "revenue": 800, "operating_cashflow": 400,
            },
        ])
        result = screener.screen(["600519", "000858"])
        assert len(result["passed"]) == 2
        assert len(result["excluded"]) == 0
        assert result["stats"]["passed_count"] == 2

    def test_all_fail(self, screener, cache):
        """所有股票都不满足条件时，全部被过滤"""
        _write_metrics(cache, [
            {
                "symbol": "688001", "name": "某ST股", "market_cap": 10,
                "pe": -5, "pb": -1, "roe": -10, "debt_ratio": 95,
                "revenue": -100, "operating_cashflow": -50,
            },
        ])
        result = screener.screen(["688001"])
        assert len(result["passed"]) == 0
        assert len(result["excluded"]) == 1
        assert result["stats"]["excluded_count"] == 1

    def test_mixed_pass_fail(self, screener, cache):
        """部分通过、部分被过滤"""
        _write_metrics(cache, [
            # 这只通过
            {
                "symbol": "600519", "name": "贵州茅台", "market_cap": 2000,
                "pe": 35, "pb": 10, "roe": 30, "debt_ratio": 30,
                "revenue": 1200, "operating_cashflow": 600,
            },
            # 这只因市值过低被过滤
            {
                "symbol": "300001", "name": "某小盘股", "market_cap": 20,
                "pe": 30, "pb": 3, "roe": 10, "debt_ratio": 40,
                "revenue": 50, "operating_cashflow": 10,
            },
        ])
        result = screener.screen(["600519", "300001"])
        assert len(result["passed"]) == 1
        assert len(result["excluded"]) == 1
        assert result["excluded"][0]["symbol"] == "300001"

    def test_empty_symbols(self, screener, cache):
        """空股票列表应返回空的通过和过滤列表"""
        result = screener.screen([])
        assert result["stats"]["total"] == 0
        assert result["stats"]["passed_count"] == 0


# ────────────────────────────────────────────
# 各维度过滤测试
# ────────────────────────────────────────────

class TestDimensionFilters:
    """逐维度测试过滤逻辑和边界值"""

    def _make_stock(self, **overrides):
        """辅助方法：生成默认通过所有维度的股票指标"""
        base = {
            "symbol": "600000", "name": "测试股票", "market_cap": 500,
            "pe": 30, "pb": 3, "roe": 15, "debt_ratio": 50,
            "revenue": 100, "operating_cashflow": 20,
        }
        base.update(overrides)
        return base

    def test_st_filter(self, screener, cache):
        """ST 股票应被过滤"""
        stock = self._make_stock(symbol="000001")
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"], realtime_data={
            "000001": {"is_st": True},
        })
        assert len(result["passed"]) == 0
        assert any("ST" in r for r in result["excluded"][0]["reasons"])

    def test_suspended_filter(self, screener, cache):
        """停牌股票应被过滤"""
        stock = self._make_stock(symbol="000002")
        _write_metrics(cache, [stock])
        result = screener.screen(["000002"], realtime_data={
            "000002": {"is_suspended": True},
        })
        assert len(result["passed"]) == 0
        assert any("停牌" in r for r in result["excluded"][0]["reasons"])

    def test_market_cap_below_min(self, screener, cache):
        """市值低于下限（50亿）应被过滤"""
        stock = self._make_stock(symbol="300001", market_cap=30)
        _write_metrics(cache, [stock])
        result = screener.screen(["300001"])
        assert len(result["excluded"]) == 1
        assert any("市值过低" in r for r in result["excluded"][0]["reasons"])

    def test_market_cap_above_max(self, screener, cache):
        """市值高于上限（5000亿）应被过滤"""
        stock = self._make_stock(symbol="600519", market_cap=6000)
        _write_metrics(cache, [stock])
        result = screener.screen(["600519"])
        assert len(result["excluded"]) == 1
        assert any("市值过高" in r for r in result["excluded"][0]["reasons"])

    def test_market_cap_at_boundary(self, screener, cache):
        """市值恰好等于下限（50亿）应通过"""
        stock = self._make_stock(symbol="600000", market_cap=50)
        _write_metrics(cache, [stock])
        result = screener.screen(["600000"])
        assert len(result["passed"]) == 1

    def test_pe_negative(self, screener, cache):
        """PE 为负（亏损股）应被过滤"""
        stock = self._make_stock(symbol="000001", pe=-5)
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"])
        assert len(result["excluded"]) == 1
        assert any("PE" in r for r in result["excluded"][0]["reasons"])

    def test_pe_above_max(self, screener, cache):
        """PE 超过上限（100）应被过滤"""
        stock = self._make_stock(symbol="000001", pe=150)
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"])
        assert any("PE" in r for r in result["excluded"][0]["reasons"])

    def test_roe_below_min(self, screener, cache):
        """ROE 低于下限（3%）应被过滤"""
        stock = self._make_stock(symbol="000001", roe=1.5)
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"])
        assert any("ROE" in r for r in result["excluded"][0]["reasons"])

    def test_debt_ratio_above_max(self, screener, cache):
        """资产负债率超过上限（80%）应被过滤"""
        stock = self._make_stock(symbol="000001", debt_ratio=85)
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"])
        assert any("负债率" in r for r in result["excluded"][0]["reasons"])

    def test_negative_cashflow(self, screener, cache):
        """经营现金流为负应被过滤"""
        stock = self._make_stock(symbol="000001", operating_cashflow=-10)
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"])
        assert any("现金流" in r for r in result["excluded"][0]["reasons"])

    def test_price_below_min(self, screener, cache):
        """股价低于 2 元应被过滤"""
        stock = self._make_stock(symbol="000001")
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"], realtime_data={
            "000001": {"price": 1.5},
        })
        assert any("价格" in r for r in result["excluded"][0]["reasons"])

    def test_limit_up_filter(self, screener, cache):
        """涨停股票应被过滤"""
        stock = self._make_stock(symbol="000001")
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"], realtime_data={
            "000001": {"is_limit_up": True},
        })
        assert any("涨停" in r for r in result["excluded"][0]["reasons"])

    def test_limit_down_filter(self, screener, cache):
        """跌停股票应被过滤"""
        stock = self._make_stock(symbol="000001")
        _write_metrics(cache, [stock])
        result = screener.screen(["000001"], realtime_data={
            "000001": {"is_limit_down": True},
        })
        assert any("跌停" in r for r in result["excluded"][0]["reasons"])


# ────────────────────────────────────────────
# 统计输出测试
# ────────────────────────────────────────────

class TestScreenerStats:
    """统计输出测试"""

    def test_dimension_breakdown(self, screener, cache):
        """dimension_breakdown 应正确统计各维度淘汰数量"""
        _write_metrics(cache, [
            # 被市值过滤
            {"symbol": "300001", "name": "小盘1", "market_cap": 10, "pe": 30, "pb": 3,
             "roe": 15, "debt_ratio": 40, "revenue": 50, "operating_cashflow": 10},
            # 被市值过滤
            {"symbol": "300002", "name": "小盘2", "market_cap": 20, "pe": 30, "pb": 3,
             "roe": 15, "debt_ratio": 40, "revenue": 50, "operating_cashflow": 10},
            # 通过
            {"symbol": "600519", "name": "茅台", "market_cap": 2000, "pe": 35, "pb": 10,
             "roe": 30, "debt_ratio": 30, "revenue": 1200, "operating_cashflow": 600},
        ])
        result = screener.screen(["300001", "300002", "600519"])

        assert result["stats"]["total"] == 3
        assert result["stats"]["passed_count"] == 1
        assert result["stats"]["excluded_count"] == 2
        # 应有市值维度淘汰 2 只
        breakdown = result["stats"]["dimension_breakdown"]
        assert "市值" in breakdown
        assert breakdown["市值"] == 2

    def test_multiple_reasons_per_stock(self, screener, cache):
        """一只股票可能因多个维度被过滤"""
        _write_metrics(cache, [
            # 同时触发：市值过低 + PE过低（亏损）+ ROE不足
            {"symbol": "300001", "name": "问题股", "market_cap": 10, "pe": -5, "pb": 0.5,
             "roe": -5, "debt_ratio": 40, "revenue": -10, "operating_cashflow": -5},
        ])
        result = screener.screen(["300001"])

        assert len(result["excluded"]) == 1
        reasons = result["excluded"][0]["reasons"]
        assert len(reasons) >= 2  # 至少触发 2 个维度

    def test_no_config_rules(self, cache, tmp_path):
        """配置文件不存在时，所有股票都应通过（无过滤规则）"""
        screener = StockScreener(cache=cache, rules_path=str(tmp_path / "nonexistent.yaml"))
        _write_metrics(cache, [
            {"symbol": "000001", "name": "任意股票", "market_cap": 1, "pe": -100, "pb": -10,
             "roe": -50, "debt_ratio": 99, "revenue": -1000, "operating_cashflow": -500},
        ])
        result = screener.screen(["000001"])
        # 没有规则，所有维度都不启用，股票应该通过
        assert len(result["passed"]) == 1
