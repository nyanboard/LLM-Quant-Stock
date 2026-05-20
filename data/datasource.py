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

    @abstractmethod
    def get_stock_metrics(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取预筛指标数据

        用于预筛模块一次性获取所有候选股票的基本面指标，避免逐只查询。
        返回的 DataFrame 包含预筛所需的全部维度数据（市值、PE、PB、ROE 等），
        由各数据源实现类负责从不同 API 聚合数据。

        Args:
            symbols: 股票代码列表（纯数字格式），如 ["600519", "000858"]

        Returns:
            DataFrame，至少包含以下列：
            - symbol: 股票代码（纯数字格式，统一由数据层转换）
            - name: 股票名称
            - industry: 行业分类
            - list_date: 上市日期
            - market_cap: 总市值（亿元）
            - pe: 市盈率 TTM
            - pb: 市净率
            - roe: 净资产收益率（%）
            - debt_ratio: 资产负债率（%）
            - revenue: 营业收入（亿元）
            - operating_cashflow: 经营现金流（亿元）

        注意：
        - akshare 和 baostock 各自能获取部分指标，两者合并后才有完整数据
        - 调用方（MetricsSyncer）负责合并两个数据源的结果
        - 股票代码必须返回纯数字格式（隐性约定）
        """
