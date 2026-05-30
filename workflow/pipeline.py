"""
主流程编排：串联预筛层 + LLM 选股层 + 量化筛选层

完整流程（7 个阶段）：
1. 获取股票池 → 2. 预筛粗筛 → 3. 批量获取数据 → 4. LLM Agent 并行分析
5. 多空辩论 + 基金经理决策 → 6. 量化二次筛选 → 7. 综合评分

新增预筛层后，流程变为：
  get_stock_list → scheduler.run_daily(预筛) → agents.analyze(从DB读取)
  → quant.filter_and_rank

设计要点：
- 预筛结果持久化到 screening_results 表，LLM 从 DB 读取候选池
- 支持断点恢复：如果预筛结果未过期，跳过预筛直接进入 LLM 分析
- skip_screener 参数允许跳过预筛（用于调试和对比实验）
- scheduler 负责数据同步 + 预筛执行，pipeline 只负责编排调用
"""
import logging
from typing import Optional

from data.cache import DataCache
from data.datasource import DataSource
from data.scheduler import DataScheduler
from data.sync import MetricsSyncer
from quant.screener import StockScreener
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

    串联 预筛 → LLM Agent 分析 → 量化二次筛选 的完整流程。
    每个阶段的中间结果都持久化到数据库，支持断点恢复。

    使用方式：
        pipeline = StockSelectionPipeline(datasource, config, cache=cache)
        picks = pipeline.run(universe="hs300")

    依赖注入：
    - datasource: 数据源（必需），用于获取股票池和行情数据
    - config: 全局配置字典（必需），包含 Agent 参数、权重等
    - cache: 数据缓存（可选），如果不传则不启用预筛和数据同步
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
            cache: 数据缓存实例。如果为 None，预筛和同步功能不启用。
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

        # 初始化预筛相关组件（仅当 cache 可用时）
        self.scheduler = None
        if cache is not None:
            screener = StockScreener(
                cache=cache,
                rules_path=config.get("screener_rules_path", "config/quant_rules.yaml"),
            )
            syncer = MetricsSyncer(datasource=datasource, cache=cache, secondary_datasource=secondary_datasource)
            self.scheduler = DataScheduler(
                datasource=datasource,
                cache=cache,
                syncer=syncer,
                screener=screener,
                realtime_source=realtime_source,
            )

    def run(
        self,
        universe: str = "hs300",
        date: Optional[str] = None,
        skip_screener: bool = False,
    ) -> list[dict]:
        """执行完整的选股流程

        完整流程：
        1. 获取/刷新预筛结果（如果启用了预筛）
        2. 从 DB 读取通过预筛的候选池
        3. LLM Agent 并行分析候选池中的股票
        4. 多空辩论 → 基金经理决策
        5. 量化二次筛选
        6. 综合评分 + 排序

        Args:
            universe: 股票池标识，如 "hs300"、"zz500"
            date: 分析日期（YYYY-MM-DD），None 表示今天
            skip_screener: 是否跳过预筛层。True 时直接对全量股票做 LLM 分析，
                          用于调试和对比预筛效果。默认 False。

        Returns:
            最终选中的股票列表，每项包含 symbol、name、total_score、reasoning 等
        """
        # ── Phase 1: 获取股票池 + 预筛 ──
        if not skip_screener and self.scheduler is not None:
            # 启用预筛：检查数据是否过期，过期则执行每日同步
            # 每日同步 = 股票池快照 → 慢数据指标同步 → 预筛执行
            if self.scheduler.is_data_stale():
                logger.info("预筛数据已过期，执行每日同步...")
                self.scheduler.run_daily(universe)
            else:
                logger.info("预筛数据未过期，直接使用缓存")

            # 从 DB 读取最新预筛结果的通过股票
            candidates = self._get_screening_candidates()
            logger.info("从预筛结果中获取 %d 只候选股票", len(candidates))
        else:
            # 跳过预筛：直接获取全量股票池
            candidates = self.datasource.get_stock_list(universe)
            logger.info("跳过预筛，使用全量股票池 %d 只", len(candidates))

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

    def _get_screening_candidates(self) -> list[str]:
        """从最新的预筛结果中获取通过筛选的股票列表

        查询 screening_stocks 表中 passed=1 的记录，
        这些股票通过了预筛的 8 个维度过滤，可以进入 LLM 分析。

        Returns:
            通过预筛的股票代码列表（纯数字格式）

        注意：
        - 如果没有任何预筛结果（从未运行过），返回空列表
        - 调用方应在此之前确保 run_daily() 已执行
        """
        if self.cache is None:
            return []

        latest = self.cache.get_latest_screening()
        if latest is None:
            logger.warning("没有找到预筛结果，请先运行每日同步")
            return []

        # 从 screening_stocks 中筛选 passed=1 的记录
        passed_stocks = [
            stock["symbol"]
            for stock in latest.get("stocks", [])
            if stock.get("passed") == 1
        ]
        return passed_stocks

    def _batch_fetch_data(self, stock_list: list[str]) -> dict:
        """批量获取股票的详细数据（K线、财报、新闻等）

        为 LLM Agent 提供分析所需的完整数据。
        预筛只需要 stock_metrics 中的基础指标，
        而 Agent 分析需要更详细的数据（历史 K 线、财报明细、新闻等）。

        Args:
            stock_list: 股票代码列表

        Returns:
            字典，键为 symbol，值为该股票的所有数据
        """
        # TODO: 批量获取数据，利用缓存
        return {}

    def _parallel_analyze(self, agent, stock_data: dict) -> list[AgentSignal]:
        """并行调用 Agent 分析

        使用 asyncio 或 ThreadPoolExecutor 实现多个 Agent 并行分析，
        减少总耗时。每个 Agent 独立处理，互不依赖。

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

        计算 RSI、MACD、布林带等技术指标，
        识别 K 线形态，供后续综合评分使用。

        Args:
            symbol: 股票代码（纯数字格式）

        Returns:
            包含技术指标和形态识别结果的字典
        """
        # TODO: 计算技术指标 + 形态识别
        return {}
