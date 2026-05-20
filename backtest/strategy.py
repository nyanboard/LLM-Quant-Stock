"""
策略封装
"""
from backtest.engine import BacktestEngine


class LLMQuantStrategy:
    """LLM 选股 + 量化筛选组合策略"""

    def __init__(self, config: dict):
        self.config = config
        self.rebalance_freq = config.get("rebalance_freq", "weekly")

    def generate_signals(self, date: str, universe: str) -> list[dict]:
        """在指定日期生成交易信号"""
        # TODO: 调用 Pipeline 执行选股
        raise NotImplementedError
