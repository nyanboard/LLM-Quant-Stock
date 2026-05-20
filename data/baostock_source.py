"""
BaoStock 数据源实现
覆盖：历史K线（多频率）、财报、基本面指标
"""
import baostock as bs
import pandas as pd
from data.datasource import DataSource


class BaoStockSource(DataSource):
    def __init__(self):
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            bs.login()
            self._logged_in = True

    def _to_baostock_code(self, symbol: str) -> str:
        """纯数字格式 → baostock 格式: 600000 → sh.600000, 000001 → sz.000001"""
        if symbol.startswith("6"):
            return f"sh.{symbol}"
        return f"sz.{symbol}"

    def get_stock_list(self, index: str) -> list[str]:
        # TODO: 获取指数成分股
        raise NotImplementedError

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        # TODO: bs.query_history_k_data_plus
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        # TODO: bs.query_profit_data / bs.query_balance_data / bs.query_cash_flow_data
        raise NotImplementedError

    def get_news(self, symbol, limit=20) -> list[dict]:
        # baostock 不提供新闻数据
        return []

    def get_money_flow(self, symbol) -> pd.DataFrame:
        # baostock 不提供资金流向数据
        return pd.DataFrame()

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        # baostock 不提供实时行情
        return pd.DataFrame()

    def __del__(self):
        if self._logged_in:
            bs.logout()
