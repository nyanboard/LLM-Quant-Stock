"""
主流程编排：串联数据同步 + LLM 选股层 + 量化筛选层

完整流程（6 个阶段）：
1. 数据同步（获取全量指标）→ 2. 从 DB 查询候选池 → 3. 批量获取数据
→ 4. LLM Agent 并行分析 → 5. 多空辩论 + 基金经理决策 → 6. 量化二次筛选

设计要点：
- stock_metrics 宽表存储全量指标（慢数据 + 实时行情），LLM 从 DB 读取候选池
- 支持断点恢复：如果指标未过期，跳过同步直接进入 LLM 分析
- scheduler 负责数据同步，pipeline 只负责编排调用
"""
import logging
from typing import Optional

from data.cache import DataCache
from data.datasource import DataSource
from data.scheduler import DataScheduler
from data.sync import MetricsSyncer
from agents.base import AgentSignal
from agents.fundamental import FundamentalAgent
from agents.sentiment import SentimentAgent
from agents.news import NewsAgent
from agents.researcher import ResearcherAgent
from agents.fund_manager import FundManagerAgent
from quant.filters import FilterEngine
from quant.scorer import Scorer

logger = logging.getLogger(__name__)


class StockSelectionPipeline:
    """选股主流程编排器

    串联 数据同步 → LLM Agent 分析 → 量化二次筛选 的完整流程。
    每个阶段的中间结果都持久化到数据库，支持断点恢复。

    使用方式：
        pipeline = StockSelectionPipeline(datasource, config, cache=cache)
        picks = pipeline.run(universe="hs300")

    依赖注入：
    - datasource: 数据源（必需），用于获取股票池和行情数据
    - config: 全局配置字典（必需），包含 Agent 参数、权重等
    - cache: 数据缓存（可选），如果不传则不启用数据同步
    """

    def __init__(
        self,
        datasource: DataSource,
        config: dict,
        cache: Optional[DataCache] = None,
        secondary_datasource: Optional[DataSource] = None,
        realtime_source=None,
    ):
        """初始化 Pipeline

        Args:
            datasource: 主数据源实例（BaoStockSource）
            config: 全局配置字典
            cache: 数据缓存实例。如果为 None，同步功能不启用。
            secondary_datasource: 辅助数据源（AkShareSource），用于合并补全字段。
            realtime_source: 实时行情数据源，需实现 get_realtime_quotes(symbols)。
        """
        self.datasource = datasource
        self.config = config
        self.cache = cache

        # 初始化 Agent（不变）
        self.fundamental = FundamentalAgent(config)
        self.sentiment = SentimentAgent(config)
        self.news_agent = NewsAgent(config)
        self.researcher = ResearcherAgent(config)
        self.fund_manager = FundManagerAgent(config)

        # 初始化量化层（不变）
        self.filter_engine = FilterEngine()
        self.scorer = Scorer(weights=config.get("score_weights"))

        # 初始化同步组件（仅当 cache 可用时）
        self.scheduler = None
        if cache is not None:
            syncer = MetricsSyncer(datasource=datasource, cache=cache, secondary_datasource=secondary_datasource)
            self.scheduler = DataScheduler(
                datasource=datasource,
                cache=cache,
                syncer=syncer,
                realtime_source=realtime_source,
            )

    def run(
        self,
        universe: str = "hs300",
        date: Optional[str] = None,
    ) -> list[dict]:
        """执行完整的选股流程

        完整流程：
        1. 检查数据是否过期，过期则执行全量同步
        2. 从 DB 查询候选股票（通过基础条件过滤）
        3. LLM Agent 并行分析候选池中的股票
        4. 多空辩论 → 基金经理决策
        5. 量化二次筛选
        6. 综合评分 + 排序

        Args:
            universe: 股票池标识，如 "hs300"、"zz500"
            date: 分析日期（YYYY-MM-DD），None 表示今天

        Returns:
            最终选中的股票列表，每项包含 symbol、name、total_score、reasoning 等
        """
        # ── Phase 1: 数据同步 ──
        if self.scheduler is not None:
            if self.scheduler.is_data_stale():
                logger.info("指标数据已过期，执行每日同步...")
                self.scheduler.run_daily(universe)
            else:
                logger.info("指标数据未过期，直接使用缓存")

            # 从 DB 查询候选股票（排除 ST、停牌等）
            candidates = self._get_candidates()
            logger.info("从 stock_metrics 中获取 %d 只候选股票", len(candidates))
        else:
            candidates = self.datasource.get_stock_list(universe)
            logger.info("无缓存，使用全量股票池 %d 只", len(candidates))

        # ── Phase 2: 批量获取数据 ──
        stock_data = self._batch_fetch_data(candidates)

        # ── Phase 3: LLM Agent 并行分析 ──
        fundamental_signals = self._parallel_analyze(self.fundamental, stock_data)
        sentiment_signals = self._parallel_analyze(self.sentiment, stock_data)
        news_signals = self._parallel_analyze(self.news_agent, stock_data)

        # ── Phase 4: 多空辩论 ──
        debate_result = self.researcher.debate(
            [fundamental_signals, sentiment_signals, news_signals],
            rounds=self.config.get("debate_rounds", 2),
        )

        # ── Phase 5: 基金经理决策 → 初选名单 ──
        shortlist = self.fund_manager.decide(
            signals=[fundamental_signals, sentiment_signals, news_signals],
            debate=debate_result,
        )

        # ── Phase 6: 量化二次筛选 ──
        for stock in shortlist:
            quant_result = self._quant_analyze(stock["symbol"])
            stock.update(quant_result)

        # ── Phase 7: 综合评分 + 过滤 ──
        final_picks = self.scorer.rank(shortlist)
        final_picks = [
            s for s in final_picks
            if self.filter_engine.apply(s).get("passed", False)
        ]

        return final_picks

    def _get_candidates(self) -> list[str]:
        """从 stock_metrics 中查询候选股票

        查询 stock_metrics 表中满足基本条件的股票（排除 ST、停牌等），
        作为 LLM 分析的候选池。

        Returns:
            候选股票代码列表（纯数字格式）
        """
        if self.cache is None:
            return []

        df = self.cache.query_metrics({"is_st": 0, "is_suspended": 0})
        if df.empty:
            logger.warning("stock_metrics 中没有符合条件的股票，请先运行同步")
            return []

        return df["symbol"].tolist()

    def _batch_fetch_data(self, stock_list: list[str]) -> dict:
        """批量获取股票的详细数据（K线、财报、新闻等）

        为 LLM Agent 提供分析所需的完整数据。

        Args:
            stock_list: 股票代码列表

        Returns:
            字典，键为 symbol，值为该股票的所有数据
        """
        # TODO: 批量获取数据，利用缓存
        return {}

    def _parallel_analyze(self, agent, stock_data: dict) -> list[AgentSignal]:
        """并行调用 Agent 分析

        Args:
            agent: Agent 实例（FundamentalAgent / SentimentAgent / NewsAgent）
            stock_data: 股票数据字典

        Returns:
            AgentSignal 列表，每只股票一个信号
        """
        # TODO: 并行调用 agent.analyze
        return []

    def _quant_analyze(self, symbol: str) -> dict:
        """对单只股票执行量化分析

        Args:
            symbol: 股票代码（纯数字格式）

        Returns:
            包含技术指标和形态识别结果的字典
        """
        # TODO: 计算技术指标 + 形态识别
        return {}
