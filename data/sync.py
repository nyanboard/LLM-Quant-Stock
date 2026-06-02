"""
预筛指标数据同步器

负责将外部数据源（akshare、baostock）的慢数据指标同步到本地 SQLite 缓存。
这些慢数据包括市值、PE/PB、ROE、负债率、营收、经营现金流等，
变化频率为日更或季更，适合每日同步一次的缓存策略。

核心逻辑：
1. 检查本地缓存是否过期（TTL 机制）
2. 过期则从数据源批量拉取最新数据
3. 写入 SQLite 的 stock_metrics 表（upsert 策略）
4. 拉取过程中加入请求间隔，防止被数据源限流

使用方式：
    syncer = MetricsSyncer(datasource=akshare_source, cache=data_cache)
    df = syncer.sync_if_stale(symbols=["600519", "000858"])
    # 返回 DataFrame，如果缓存未过期则直接返回缓存数据

与 DataScheduler 的关系：
    MetricsSyncer 只负责数据同步，不负责触发时机。
    DataScheduler 负责每日定时调用 MetricsSyncer + Screener + 持久化结果。
"""
import logging
import time
from typing import Optional

import pandas as pd

from data.cache import DataCache
from data.datasource import DataSource

logger = logging.getLogger(__name__)


class MetricsSyncer:
    """预筛指标同步器

    从外部数据源批量拉取慢数据指标，写入本地 SQLite 缓存。
    支持 TTL 过期检查、限流保护、失败重试、部分失败容忍。

    设计决策：
    - 使用 "全量替换" 策略：每次同步时获取所有 symbols 的完整数据，
      然后 upsert 到 stock_metrics 表，覆盖旧数据。
    - 不做增量同步，因为慢数据体量不大（300-500 条），全量同步简单可靠。
    """

    def __init__(
        self,
        datasource: DataSource,
        cache: DataCache,
        secondary_datasource: Optional["DataSource"] = None,
        request_interval: float = 0.4,
        max_retries: int = 3,
    ):
        """初始化同步器

        Args:
            datasource: 主数据源实例，用于调用 get_stock_metrics() 获取指标数据
            cache: 数据缓存实例，用于读写 stock_metrics 表
            secondary_datasource: 辅助数据源（可选），与主数据源合并以补全字段
            request_interval: 请求间隔时间（秒），默认 0.4 秒。
            max_retries: 单只股票获取失败时的最大重试次数，默认 3 次。
        """
        self.datasource = datasource
        self.secondary_datasource = secondary_datasource
        self.cache = cache
        self.request_interval = request_interval
        self.max_retries = max_retries

    def sync_if_stale(
        self, symbols: list[str], ttl: int = 86400
    ) -> Optional[pd.DataFrame]:
        """检查缓存是否过期，过期则从数据源重新同步

        这是同步器的主入口方法，调用流程：
        1. 尝试从 cache.get_metrics() 获取缓存数据
        2. 如果缓存有效（未过期且包含所有 symbols），直接返回
        3. 如果缓存过期或不存在，调用 _fetch_with_retry() 拉取数据
        4. 拉取成功后写入缓存并返回

        Args:
            symbols: 需要同步指标的股票代码列表（纯数字格式）
            ttl: 缓存有效期（秒），默认 86400（1 天）。
                设为 0 可强制刷新。

        Returns:
            包含所有股票指标的 DataFrame。
            如果数据源完全不可用（所有股票都获取失败），返回 None。
        """
        # Step 1: 尝试从缓存获取
        cached = self.cache.get_metrics(symbols, ttl=ttl)
        if cached is not None:
            logger.info(
                "缓存命中，跳过同步。共 %d 只股票，缓存时间戳: %s",
                len(cached),
                cached["synced_at"].iloc[0] if len(cached) > 0 else "N/A",
            )
            return cached

        # Step 2: 缓存过期或不存在，从数据源拉取
        logger.info("缓存过期或不存在，开始同步 %d 只股票的指标数据", len(symbols))
        df = self._fetch_with_retry(symbols)

        if df is None or df.empty:
            logger.warning("同步失败，未能获取任何股票指标数据")
            return None

        # Step 3: 写入缓存
        # 添加 synced_at 时间戳，标记本次同步时间
        df = df.copy()
        df["synced_at"] = time.time()
        self.cache.upsert_metrics(df)
        logger.info("同步完成，成功写入 %d 只股票的指标数据", len(df))

        return df

    def _merge_metrics(
        self, primary: pd.DataFrame, secondary: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """合并两个数据源的指标数据

        按symbol做outer join，primary优先，用secondary填补primary中的None。
        同时合并实时行情字段（is_st, is_suspended, is_limit_up, is_limit_down,
        price, turnover_rate, avg_amount）。
        """
        if secondary is None or secondary.empty:
            return primary
        if primary.empty:
            return secondary

        metric_cols = [
            "name", "industry", "list_date", "market_cap", "pe", "pb",
            "roe", "debt_ratio", "revenue", "operating_cashflow",
            "is_st", "is_suspended", "is_limit_up", "is_limit_down",
            "price", "turnover_rate", "avg_amount",
        ]

        merged = primary.merge(secondary, on="symbol", how="outer", suffixes=("", "_sec"))
        for col in metric_cols:
            sec_col = f"{col}_sec"
            if sec_col in merged.columns:
                merged[col] = merged[col].fillna(merged[sec_col])
                merged.drop(columns=[sec_col], inplace=True)

        if "synced_at_sec" in merged.columns:
            merged["synced_at"] = merged["synced_at"].combine_first(merged["synced_at_sec"])
            merged.drop(columns=["synced_at_sec"], inplace=True)

        return merged

    @staticmethod
    def realtime_df_to_dict(df: pd.DataFrame) -> dict[str, dict]:
        """将实时行情 DataFrame 转为 screener 期望的 dict 格式

        Args:
            df: get_realtime_quotes() 返回的 DataFrame

        Returns:
            {"600519": {"is_st": False, "price": 1800.0, ...}, ...}
        """
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            symbol = row.get("symbol")
            if symbol:
                result[symbol] = {
                    "is_st": bool(row.get("is_st", False)),
                    "is_suspended": bool(row.get("is_suspended", False)),
                    "is_limit_up": bool(row.get("is_limit_up", False)),
                    "is_limit_down": bool(row.get("is_limit_down", False)),
                    "price": row.get("price"),
                    "turnover_rate": row.get("turnover_rate"),
                    "avg_amount": row.get("avg_amount"),
                }
        return result

    def _fetch_with_retry(self, symbols: list[str]) -> Optional[pd.DataFrame]:
        """带重试和限流保护的数据拉取

        策略：
        1. 调用 datasource.get_stock_metrics(symbols) 批量获取慢数据
        2. 调用 secondary_datasource.get_realtime_quotes(symbols) 获取实时行情
        3. 合并慢数据 + 实时数据到一个 DataFrame
        4. 如果失败，等待 request_interval 后重试，最多 max_retries 次

        实时数据获取失败不阻塞慢数据返回，实时字段置为 None。

        Args:
            symbols: 股票代码列表

        Returns:
            合并后的指标 DataFrame（含慢数据 + 实时字段），全部失败返回 None
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "第 %d/%d 次尝试获取指标数据（%d 只股票）",
                    attempt, self.max_retries, len(symbols),
                )
                df = self.datasource.get_stock_metrics(symbols)
                if df is None:
                    df = pd.DataFrame()

                # 从辅助数据源获取慢数据并合并
                if self.secondary_datasource is not None:
                    try:
                        df_sec = self.secondary_datasource.get_stock_metrics(symbols)
                        if df_sec is not None and not df_sec.empty:
                            df = self._merge_metrics(df, df_sec)
                            logger.info("双数据源慢数据合并完成")
                    except Exception as e:
                        logger.warning("辅助数据源获取失败，仅使用主数据源: %s", str(e))

                # 获取实时行情数据并合并
                if self.secondary_datasource is not None:
                    try:
                        rt_df = self.secondary_datasource.get_realtime_quotes(symbols)
                        if rt_df is not None and not rt_df.empty:
                            df = self._merge_metrics(df, rt_df)
                            logger.info("实时行情数据合并完成（%d 只）", len(rt_df))
                    except Exception as e:
                        logger.warning("实时行情获取失败，实时字段将为空: %s", str(e))

                if df is not None and not df.empty:
                    return df

                logger.warning(
                    "第 %d 次尝试返回空数据，可能是数据源暂时不可用", attempt
                )

            except Exception as e:
                last_error = e
                logger.error(
                    "第 %d 次尝试失败: %s", attempt, str(e)
                )

            # 重试前等待（最后一次失败后不需要等待）
            if attempt < self.max_retries:
                wait_time = self.request_interval * attempt
                logger.info("等待 %.1f 秒后重试...", wait_time)
                time.sleep(wait_time)

        # 所有重试都失败
        if last_error:
            logger.error(
                "同步失败，已重试 %d 次。最后一次错误: %s",
                self.max_retries, str(last_error),
            )
        return None
