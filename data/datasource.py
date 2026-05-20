"""
统一数据源抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class DataSource(ABC):
    """数据源抽象基类，所有数据源必须实现此接口"""

    @abstractmethod
    def get_stock_list(self, index: str) -> list[str]:
        """获取指数成分股列表（纯数字格式）"""

    @abstractmethod
    def get_daily_quotes(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取日K线数据
        Args:
            symbol: 股票代码（纯数字格式）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust: 复权方式 qfq/hfq/None
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """

    @abstractmethod
    def get_financial_report(
        self,
        symbol: str,
        report_type: str = "income",
        period: Optional[str] = None,
    ) -> dict:
        """获取财报数据
        Args:
            report_type: income/balance/cashflow
        """

    @abstractmethod
    def get_news(self, symbol: str, limit: int = 20) -> list[dict]:
        """获取个股新闻"""

    @abstractmethod
    def get_money_flow(self, symbol: str) -> pd.DataFrame:
        """获取资金流向数据"""

    @abstractmethod
    def get_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """获取实时行情快照"""
