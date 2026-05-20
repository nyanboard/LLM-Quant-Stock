"""
回测报告生成
"""
from backtest.engine import BacktestEngine


class BacktestReport:
    def generate(self, result: dict, output_format: str = "markdown") -> str:
        """生成回测报告"""
        # TODO: 生成 Markdown/HTML 报告
        raise NotImplementedError
