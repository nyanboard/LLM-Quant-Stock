"""
AkShare 数据源实现
覆盖：实时行情、资金流向、龙虎榜、新闻、行业分类
"""
import pandas as pd
from data.datasource import DataSource


class AkShareSource(DataSource):
    def __init__(self):
        # TODO: 初始化 akshare
        pass

    def get_stock_list(self, index: str) -> list[str]:
        # TODO: akshare 获取指数成分股
        raise NotImplementedError

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        # TODO: ak.stock_zh_a_hist
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        # TODO: ak.stock_financial_report_sina
        raise NotImplementedError

    def get_news(self, symbol, limit=20) -> list[dict]:
        # TODO: ak.stock_news_em
        raise NotImplementedError

    def get_money_flow(self, symbol) -> pd.DataFrame:
        # TODO: ak.stock_individual_fund_flow
        raise NotImplementedError

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        # TODO: ak.stock_zh_a_spot_em
        raise NotImplementedError
