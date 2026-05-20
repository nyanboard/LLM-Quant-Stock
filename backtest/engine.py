"""
回测引擎
"""
import pandas as pd


class BacktestEngine:
    def __init__(self, config: dict):
        self.initial_cash = config.get("initial_cash", 1_000_000)
        self.commission_rate = config.get("commission_rate", 0.001)
        self.slippage = config.get("slippage", 0.001)
        self.benchmark = config.get("benchmark", "hs300")

    def run(self, strategy_signals: list[dict], price_data: pd.DataFrame) -> dict:
        """运行回测
        Args:
            strategy_signals: 选股信号列表
            price_data: 价格数据
        Returns:
            {"metrics": {...}, "equity_curve": [...], "trades": [...]}
        """
        # TODO: 实现回测逻辑
        raise NotImplementedError

    def calc_metrics(self, equity_curve: pd.Series) -> dict:
        """计算回测绩效指标"""
        # TODO: 累计收益、年化收益、最大回撤、夏普比率、胜率
        raise NotImplementedError
