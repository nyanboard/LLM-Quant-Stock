"""
每日数据同步调度器

负责每日收盘后执行全量指标同步：
1. 获取股票列表（全 A 或指定指数成分股）
2. 同步全量指标（慢数据 + 实时行情）写入 stock_metrics 宽表

执行时机：
- 定时触发：每日 15:30（A 股收盘后），由外部调度器或前端定时开关触发
- 手动触发：通过 API（POST /api/v1/metrics/sync）或 CLI 触发
- 兜底触发：Pipeline 启动时检测到数据过期（>1天），自动补跑

设计原则：
- 顺序执行：确保数据时点一致性
- 幂等安全：多次执行只覆盖 stock_metrics（UPSERT），不累积历史
- 容错：实时数据源失败不阻塞慢数据同步

数据流：
    datasource.get_stock_list(universe)
        → syncer.sync_if_stale(symbols)     # 慢数据 + 实时行情合并写入 stock_metrics 表
"""
import logging
import time
from typing import Optional

from data.cache import DataCache
from data.datasource import DataSource
from data.sync import MetricsSyncer

logger = logging.getLogger(__name__)


class DataScheduler:
    """每日数据同步调度器

    串联 获取股票列表 → 全量指标同步 的完整流程。
    syncer 内部会将慢数据（PE/PB/ROE 等）和实时数据（ST/停牌/涨跌停/价格）合并写入 stock_metrics。

    使用方式：
        scheduler = DataScheduler(
            datasource=baostock_source,
            cache=data_cache,
            syncer=metrics_syncer,
            realtime_source=akshare_source,
        )
        result = scheduler.run_daily(universe="hs300")
    """

    def __init__(
        self,
        datasource: DataSource,
        cache: DataCache,
        syncer: MetricsSyncer,
        realtime_source=None,
    ):
        """初始化调度器

        Args:
            datasource: 数据源实例，用于获取股票池列表（get_stock_list）
            cache: 数据缓存实例
            syncer: 指标同步器，用于同步全量指标到 stock_metrics 表
            realtime_source: 实时行情数据源（可选），用于获取 ST/停牌/涨跌停状态
        """
        self.datasource = datasource
        self.cache = cache
        self.syncer = syncer
        self.realtime_source = realtime_source

    def run_daily(
        self, universe: str = "hs300"
    ) -> Optional[dict]:
        """执行每日同步流程（获取股票列表 → 全量指标同步）

        Args:
            universe: 指数标识，默认 "hs300"（沪深300）。
                     常见选项：hs300/zz500/zz1000/sza（全A）

        Returns:
            同步结果字典：
            {"synced_count": 300, "universe": "hs300"}
            失败返回 None
        """
        logger.info("===== 开始每日同步流程（universe=%s）=====", universe)

        # ── Step 1: 获取股票列表 ──
        logger.info("Step 1: 获取股票列表")
        try:
            symbols = self.datasource.get_stock_list(universe)
            logger.info("股票列表获取完成: universe=%s, 共 %d 只", universe, len(symbols))
        except Exception as e:
            logger.error("股票列表获取失败: %s", str(e))
            return None

        # ── Step 2: 同步全量指标（慢数据 + 实时行情）──
        # MetricsSyncer 内部会合并两个数据源并 UPSERT 到 stock_metrics
        logger.info("Step 2: 同步全量指标（%d 只股票）", len(symbols))
        try:
            metrics_df = self.syncer.sync_if_stale(symbols)
            if metrics_df is not None:
                logger.info("指标同步完成: 共 %d 只股票", len(metrics_df))
                return {"synced_count": len(metrics_df), "universe": universe}
            else:
                logger.warning("指标同步返回空数据")
                return {"synced_count": 0, "universe": universe}
        except Exception as e:
            logger.error("指标同步失败: %s", str(e))
            return None

    def is_data_stale(self, ttl: int = 86400) -> bool:
        """检查 stock_metrics 数据是否已过期

        用于 Pipeline 启动时的兜底检测：如果最新数据超过 TTL，
        Pipeline 应该先调用 run_daily() 刷新数据。

        Args:
            ttl: 有效期（秒），默认 86400（1 天）

        Returns:
            True 表示数据已过期，需要重新同步
        """
        status = self.cache.get_sync_status()
        if status["total_count"] == 0:
            return True
        if status["last_synced_at"] is None:
            return True
        elapsed = time.time() - status["last_synced_at"]
        return elapsed > ttl
