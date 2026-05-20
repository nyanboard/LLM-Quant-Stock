"""
主流程编排：串联 LLM 选股层 + 量化筛选层
"""
from data.datasource import DataSource
from agents.base import AgentSignal
from agents.fundamental import FundamentalAgent
from agents.sentiment import SentimentAgent
from agents.news import NewsAgent
from agents.researcher import ResearcherAgent
from agents.fund_manager import FundManagerAgent
from quant.filters import FilterEngine
from quant.scorer import Scorer


class StockSelectionPipeline:
    def __init__(self, datasource: DataSource, config: dict):
        self.datasource = datasource
        self.config = config

        # 初始化 Agent
        self.fundamental = FundamentalAgent(config)
        self.sentiment = SentimentAgent(config)
        self.news_agent = NewsAgent(config)
        self.researcher = ResearcherAgent(config)
        self.fund_manager = FundManagerAgent(config)

        # 初始化量化层
        self.filter_engine = FilterEngine()
        self.scorer = Scorer(weights=config.get("score_weights"))

    def run(self, universe: str = "hs300", date: str | None = None) -> list[dict]:
        """执行完整的选股流程"""

        # Phase 1: 获取股票池
        stock_list = self.datasource.get_stock_list(universe)

        # Phase 2: 批量获取数据
        stock_data = self._batch_fetch_data(stock_list)

        # Phase 3: LLM Agent 并行分析
        fundamental_signals = self._parallel_analyze(self.fundamental, stock_data)
        sentiment_signals = self._parallel_analyze(self.sentiment, stock_data)
        news_signals = self._parallel_analyze(self.news_agent, stock_data)

        # Phase 4: 多空辩论
        debate_result = self.researcher.debate(
            [fundamental_signals, sentiment_signals, news_signals],
            rounds=self.config.get("debate_rounds", 2),
        )

        # Phase 5: 基金经理决策 → 初选名单
        shortlist = self.fund_manager.decide(
            signals=[fundamental_signals, sentiment_signals, news_signals],
            debate=debate_result,
        )

        # Phase 6: 量化二次筛选
        for stock in shortlist:
            quant_result = self._quant_analyze(stock["symbol"])
            stock.update(quant_result)

        # Phase 7: 综合评分 + 过滤
        final_picks = self.scorer.rank(shortlist)
        final_picks = [s for s in final_picks if self.filter_engine.apply(s).get("passed", False)]

        return final_picks

    def _batch_fetch_data(self, stock_list: list[str]) -> dict:
        # TODO: 批量获取数据，利用缓存
        return {}

    def _parallel_analyze(self, agent, stock_data: dict) -> list[AgentSignal]:
        # TODO: 并行调用 agent.analyze
        return []

    def _quant_analyze(self, symbol: str) -> dict:
        # TODO: 计算技术指标 + 形态识别
        return {}
