"""
每日定时同步调度器

负责每日收盘后按顺序执行三项同步任务：
1. 同步股票池快照（哪些股票在 HS300/ZZ500 中）
2. 同步慢数据指标（市值、PE/PB、ROE 等基本面数据）
3. 执行预筛并持久化结果

执行时机：
- 定时触发：每日 15:30（A 股收盘后），由外部调度器（cron/APScheduler）调用
- 手动触发：通过 API（POST /api/v1/screener/run）或 CLI 触发
- 兜底触发：Pipeline 启动时检测到数据过期（>1天），自动补跑

设计原则：
- 顺序执行，不并行：确保数据时点一致性（股票池 → 指标 → 预筛 使用同一批数据）
- 每步结果都持久化：即使后续步骤失败，前面的结果也不会丢失
- 幂等安全：同一天多次执行，会产生新的快照记录（不会覆盖历史）

数据流：
    datasource.get_stock_list("hs300")
        → cache.save_stock_pool()           # 写入 stock_pools 表
        → syncer.sync_if_stale(symbols)     # 写入 stock_metrics 表
        → screener.screen(symbols)          # 执行 8 维度预筛
        → cache.save_screening_result()     # 写入 screening_results + screening_stocks 表
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

    串联 股票池同步 → 指标同步 → 预筛执行 的完整流程。
    每次执行产生一组新的不可变快照数据，供后续 LLM Agent 消费。

    使用方式：
        scheduler = DataScheduler(
            datasource=akshare_source,
            cache=data_cache,
            syncer=metrics_syncer,
            screener=stock_screener,
        )
        result = scheduler.run_daily(universe="hs300")

    依赖关系：
    - DataScheduler 不直接依赖 quant.screener 的具体实现类，
      而是依赖一个具有 screen(symbols) 方法的对象（鸭子类型），
      降低模块间耦合。
    """

    def __init__(
        self,
        datasource: DataSource,
        cache: DataCache,
        syncer: MetricsSyncer,
        screener=None,
        realtime_source=None,
    ):
        """初始化调度器

        Args:
            datasource: 数据源实例，用于获取股票池列表（get_stock_list）
            cache: 数据缓存实例，用于保存股票池快照和预筛结果
            syncer: 指标同步器，用于同步慢数据到 stock_metrics 表
            screener: 预筛器实例（可选），需实现 screen(symbols) 方法。
            realtime_source: 实时行情数据源（可选），需实现 get_realtime_quotes(symbols)。
        """
        self.datasource = datasource
        self.cache = cache
        self.syncer = syncer
        self.screener = screener
        self.realtime_source = realtime_source

    def run_daily(
        self, universe: str = "hs300"
    ) -> Optional[dict]:
        """执行每日同步流程（股票池 → 指标 → 预筛）

        完整流程：
        1. 从数据源获取最新的指数成分股列表
        2. 将成分股列表保存为股票池快照（stock_pools 表）
        3. 批量同步这些股票的慢数据指标（stock_metrics 表）
        4. 如果配置了预筛器，执行预筛并保存结果（screening_results 表）

        每个步骤都是独立的，即使后续步骤失败，前面的结果也会持久化。
        例如：如果预筛器出错，股票池快照和指标数据仍然可用，
        下次重新执行时可以直接跳过已同步的步骤。

        Args:
            universe: 指数标识，默认 "hs300"（沪深300）。
                     支持的值取决于数据源实现，常见选项：
                     - "hs300": 沪深300
                     - "zz500": 中证500
                     - "sz50":  上证50

        Returns:
            预筛结果字典（如果成功执行了预筛步骤），格式：
            {
                "screening_id": 42,
                "pool_id": 15,
                "universe": "hs300",
                "passed_count": 85,
                "excluded_count": 215,
                "total_count": 300,
            }
            如果未配置预筛器或预筛失败，返回 None（但前两步的结果已持久化）。
        """
        logger.info("===== 开始每日同步流程（universe=%s）=====", universe)

        # ── Step 1: 同步股票池快照 ──
        # 获取当前指数的成分股列表，保存为一条新的 stock_pools 记录
        # 每次都是新记录，不覆盖历史，支持回溯
        logger.info("Step 1: 同步股票池快照")
        try:
            symbols = self.datasource.get_stock_list(universe)
            pool_id = self.cache.save_stock_pool(universe, symbols)
            logger.info(
                "股票池同步完成: universe=%s, 共 %d 只成分股, pool_id=%d",
                universe, len(symbols), pool_id,
            )
        except Exception as e:
            logger.error("股票池同步失败: %s", str(e))
            return None

        # ── Step 2: 同步慢数据指标 ──
        # 批量拉取成分股的市值、PE/PB、ROE 等指标
        # 如果缓存未过期（TTL=1天），这一步会跳过 API 调用直接返回缓存
        # MetricsSyncer 内部有重试和限流保护
        logger.info("Step 2: 同步慢数据指标（%d 只股票）", len(symbols))
        try:
            metrics_df = self.syncer.sync_if_stale(symbols)
            if metrics_df is not None:
                logger.info("指标同步完成: 共 %d 只股票", len(metrics_df))
            else:
                logger.warning("指标同步返回空数据，预筛可能不完整")
        except Exception as e:
            logger.error("指标同步失败: %s", str(e))
            # 指标同步失败不阻断流程，预筛可以使用旧缓存数据
            # 但如果完全没有数据，预筛结果可能不准确

        # ── Step 3: 执行预筛 ──
        # 调用 screener.screen() 对成分股进行 8 维度预筛
        # 结果持久化到 screening_results + screening_stocks 表
        if self.screener is None:
            logger.info("Step 3: 未配置预筛器，跳过预筛步骤")
            return {
                "screening_id": None,
                "pool_id": pool_id,
                "universe": universe,
                "total_count": len(symbols),
                "passed_count": None,
                "excluded_count": None,
            }

        logger.info("Step 3: 执行预筛")
        try:
            # 获取实时行情数据
            realtime_data = {}
            if self.realtime_source is not None:
                try:
                    rt_df = self.realtime_source.get_realtime_quotes(symbols)
                    realtime_data = MetricsSyncer.realtime_df_to_dict(rt_df)
                    logger.info("实时行情获取完成: %d 只股票", len(realtime_data))
                except Exception as e:
                    logger.warning("实时行情获取失败，预筛将仅使用慢数据: %s", str(e))

            screen_result = self.screener.screen(symbols, realtime_data=realtime_data)
            screening_id = self.cache.save_screening_result(screen_result, pool_id=pool_id)
            logger.info(
                "预筛完成: screening_id=%d, 通过 %d 只, 过滤 %d 只",
                screening_id,
                screen_result["stats"]["passed_count"],
                screen_result["stats"]["excluded_count"],
            )
            return {
                "screening_id": screening_id,
                "pool_id": pool_id,
                "universe": universe,
                "total_count": screen_result["stats"]["total"],
                "passed_count": screen_result["stats"]["passed_count"],
                "excluded_count": screen_result["stats"]["excluded_count"],
            }
        except Exception as e:
            logger.error("预筛执行失败: %s", str(e))
            return None

    def is_data_stale(self, ttl: int = 86400) -> bool:
        """检查最新的预筛结果是否已过期

        用于 Pipeline 启动时的兜底检测：如果最新的预筛结果超过 TTL，
        Pipeline 应该先调用 run_daily() 刷新数据，再进行后续分析。

        判断逻辑：
        - 如果 screening_results 表为空（从未执行过预筛），视为过期
        - 如果最新记录的 created_at 距今超过 TTL，视为过期

        Args:
            ttl: 有效期（秒），默认 86400（1 天）

        Returns:
            True 表示数据已过期，需要重新同步
        """
        latest = self.cache.get_latest_screening()
        if latest is None:
            # 从未执行过预筛，数据肯定是"过期的"
            return True
        # 检查最新预筛记录的时间戳
        elapsed = time.time() - latest["created_at"]
        return elapsed > ttl
