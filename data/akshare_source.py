"""
AkShare 数据源实现

覆盖能力：
- 实时行情（stock_zh_a_spot_em）
- 资金流向（stock_individual_fund_flow）
- 龙虎榜（stock_lhb_detail_em）
- 新闻（stock_news_em）
- 行业分类（stock_board_industry_name_em）
- 预筛指标（stock_zh_a_spot_em 提供市值/PE/PB 等实时指标）

AkShare 特点：
- 免费开源，无需注册 API Key
- 数据主要来自东方财富、新浪财经等公开数据源
- 覆盖 A 股全市场，实时性较好
- 注意：频繁请求可能触发上游数据源的反爬机制，需要控制请求频率

股票代码格式约定：
- AkShare 内部使用纯数字格式（如 "000001"），与本项目的统一格式一致
- 因此在本实现中不需要做代码格式转换
"""
import pandas as pd
from data.datasource import DataSource


class AkShareSource(DataSource):
    """AkShare 数据源实现

    使用前需安装 akshare：pip install akshare
    """

    def __init__(self):
        # TODO: 初始化 akshare（如有需要可在此配置请求头、代理等）
        pass

    # 指数代码映射：项目标识 → 中证指数代码
    _INDEX_MAP = {
        "hs300": "000300",
        "zz500": "000905",
        "zz1000": "000852",
        "sz50": "000016",
    }

    def get_stock_list(self, index: str) -> list[str]:
        """获取指数成分股列表

        通过 AkShare 的 index_stock_cons_csindex 接口查询中证指数公司公布的成分股。

        Args:
            index: 指数标识，如 "hs300"（沪深300）、"zz500"（中证500）

        Returns:
            成分股代码列表（纯数字格式），如 ["600519", "000858", ...]
        """
        import akshare as ak

        if index == "sza":
            # 全 A 股：获取所有 A 股列表
            df = ak.stock_zh_a_spot_em()
            return df["代码"].tolist()

        csindex_code = self._INDEX_MAP.get(index)
        if csindex_code is None:
            raise ValueError(f"不支持的指数: {index}，支持: {list(self._INDEX_MAP.keys())}, sza")

        df = ak.index_stock_cons_csindex(symbol=csindex_code)
        # 返回的列名是"成分券代码"，已经是纯数字格式
        return df["成分券代码"].tolist()

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        """获取日K线数据

        Args:
            symbol: 股票代码（纯数字格式）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust: 复权方式 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)
        """
        # TODO: ak.stock_zh_a_hist(symbol, period="daily", start_date, end_date, adjust)
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        """获取财报数据

        Args:
            symbol: 股票代码
            report_type: "income"(利润表) / "balance"(资产负债表) / "cashflow"(现金流量表)
            period: 报告期，如 "2024-12-31"
        """
        # TODO: ak.stock_financial_report_sina(stock=symbol, symbol=report_type)
        raise NotImplementedError

    def get_news(self, symbol, limit=20) -> list[dict]:
        """获取个股新闻

        Args:
            symbol: 股票代码
            limit: 返回数量上限
        """
        # TODO: ak.stock_news_em(symbol=symbol)
        raise NotImplementedError

    def get_money_flow(self, symbol) -> pd.DataFrame:
        """获取资金流向数据"""
        # TODO: ak.stock_individual_fund_flow(stock=symbol, market="sh"/"sz")
        raise NotImplementedError

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        """获取实时行情快照

        Args:
            symbols: 股票代码列表（纯数字格式）

        Returns:
            DataFrame 包含最新价、涨跌幅、成交量、换手率等实时数据
        """
        # TODO: ak.stock_zh_a_spot_em()，然后 filter by symbols
        raise NotImplementedError

    def get_stock_metrics(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取预筛指标（AkShare 部分）

        从 AkShare 的 stock_zh_a_spot_em 接口获取全市场实时行情，
        提取市值、PE、PB 等指标。一次调用获取全部约 5000 只 A 股。

        注意：AkShare 不提供 ROE、负债率、现金流等财报指标，
        这些由 BaoStockSource.get_stock_metrics() 补充。
        """
        import time

        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        df = df[df["代码"].isin(symbols)]

        result = pd.DataFrame({
            "symbol": df["代码"],
            "name": df["名称"],
            "industry": None,
            "list_date": None,
            "market_cap": df["总市值"] / 1e8,
            "pe": df["市盈率-动态"],
            "pb": df["市净率"],
            "roe": None,
            "debt_ratio": None,
            "revenue": None,
            "operating_cashflow": None,
            "synced_at": time.time(),
        })
        return result
