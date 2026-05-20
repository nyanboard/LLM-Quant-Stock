"""
BaoStock 数据源实现

覆盖能力：
- 历史日K线（多频率：日/周/月），query_history_k_data_plus
- 财报数据（利润表、资产负债表、现金流量表）
- 基本面指标（ROE、资产负债率、营业收入、经营现金流等）
- 指数成分股查询

不覆盖（由 AkShare 负责）：
- 实时行情、资金流向、龙虎榜、新闻、行业分类

BaoStock 特点：
- 免费开源，专注历史数据和财报
- 数据稳定，复权数据准确
- 需要先 login() 才能查询，用完后 logout()
- 请求频率建议控制在 0.3 秒以上，避免被限流

股票代码格式约定：
- BaoStock 内部使用带前缀格式：sh.600000（上交所）、sz.000001（深交所）
- 本项目的统一格式是纯数字：600000、000001
- 所有 public 方法接收和返回纯数字格式，内部通过 _to_baostock_code() 转换
"""
import time

import baostock as bs
import pandas as pd
from data.datasource import DataSource


class BaoStockSource(DataSource):
    """BaoStock 数据源实现

    使用前需安装 baostock：pip install baostock

    注意：BaoStock 使用 login/logout 模式，本类在首次查询时自动登录，
    在对象销毁时自动登出。避免频繁创建/销毁实例。
    """

    def __init__(self):
        # 登录状态标记，延迟到首次查询时才真正登录（避免初始化时网络延迟）
        self._logged_in = False

    def _ensure_login(self):
        """确保已登录 BaoStock 服务

        BaoStock 要求在查询数据前先调用 bs.login()。
        采用延迟登录策略：只在首次实际查询时登录，而不是在 __init__ 中登录，
        这样在仅创建实例但未使用的场景下不会产生不必要的网络连接。
        """
        if not self._logged_in:
            bs.login()
            self._logged_in = True

    def _to_baostock_code(self, symbol: str) -> str:
        """将纯数字格式的股票代码转换为 BaoStock 格式

        转换规则：
        - 6 开头 → sh. 前缀（上交所，如 600000 → sh.600000）
        - 0 或 3 开头 → sz. 前缀（深交所，如 000001 → sz.000001）
        - 其他（如 8 开头的北交所）→ sz. 前缀（BaoStock 暂不完全支持北交所）

        Args:
            symbol: 纯数字格式的股票代码，如 "600519"

        Returns:
            BaoStock 格式的代码，如 "sh.600519"
        """
        if symbol.startswith("6"):
            return f"sh.{symbol}"
        return f"sz.{symbol}"

    def _to_pure_code(self, baostock_code: str) -> str:
        """将 BaoStock 格式的代码转换回纯数字格式

        Args:
            baostock_code: BaoStock 格式代码，如 "sh.600519"

        Returns:
            纯数字格式，如 "600519"
        """
        # 去掉 "sh." 或 "sz." 前缀
        return baostock_code.split(".")[-1]

    # 指数标识 → BaoStock 查询方法名
    _INDEX_QUERY_MAP = {
        "hs300": "query_hs300_stocks",
        "zz500": "query_zz500_stocks",
        "sz50": "query_sz50_stocks",
    }

    def get_stock_list(self, index: str) -> list[str]:
        """获取指数成分股列表

        通过 BaoStock 的 query_hs300_stocks() 等接口获取成分股。

        Args:
            index: 指数标识，如 "hs300"→沪深300, "zz500"→中证500, "sz50"→上证50

        Returns:
            成分股代码列表（纯数字格式），如 ["600519", "000858", ...]
        """
        self._ensure_login()

        if index == "sza":
            # 全 A 股：query_all_stock 返回当日所有证券
            rs = bs.query_all_stock(day=pd.Timestamp.now().strftime("%Y-%m-%d"))
            stocks = []
            while rs.error_code == "0" and rs.next():
                code = rs.get_row_data()[1]  # code 列，格式 sh.600000
                # 只保留 A 股（排除指数、基金、债券等）
                if code and code.startswith(("sh.6", "sz.0", "sz.3")):
                    stocks.append(self._to_pure_code(code))
            return stocks

        method_name = self._INDEX_QUERY_MAP.get(index)
        if method_name is None:
            raise ValueError(f"不支持的指数: {index}，支持: {list(self._INDEX_QUERY_MAP.keys())}, sza")

        query_fn = getattr(bs, method_name)
        rs = query_fn()

        stocks = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            # BaoStock 返回的 code 格式是 sh.600000，需要转为纯数字
            stocks.append(self._to_pure_code(row[1]))

        return stocks

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        """获取历史日K线数据

        BaoStock 的 query_history_k_data_plus 接口支持前复权/后复权，
        复权数据准确，适合回测使用。

        Args:
            symbol: 股票代码（纯数字格式），内部会转为 baostock 格式
            start_date: 开始日期，如 "2024-01-01"
            end_date: 结束日期，如 "2024-12-31"
            adjust: 复权方式 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)

        Returns:
            DataFrame 包含 date, open, high, low, close, volume, amount 等列
        """
        # TODO: bs.query_history_k_data_plus(self._to_baostock_code(symbol), fields, ...)
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        """获取财报数据

        BaoStock 提供三种财报查询接口：
        - bs.query_profit_data() → 利润表（营收、净利润、ROE 等）
        - bs.query_balance_data() → 资产负债表（总资产、总负债、资产负债率等）
        - bs.query_cash_flow_data() → 现金流量表（经营/投资/筹资现金流等）

        Args:
            symbol: 股票代码（纯数字格式）
            report_type: "income" / "balance" / "cashflow"
            period: 报告期，如 "2024-12-31"（不指定则取最新一期）
        """
        # TODO: 根据 report_type 调用对应接口
        raise NotImplementedError

    def get_news(self, symbols, limit=20) -> list[dict]:
        """获取个股新闻

        BaoStock 不提供新闻数据，返回空列表。
        新闻数据由 AkShareSource.get_news() 提供。
        """
        return []

    def get_money_flow(self, symbol) -> pd.DataFrame:
        """获取资金流向数据

        BaoStock 不提供资金流向数据，返回空 DataFrame。
        资金流向由 AkShareSource.get_money_flow() 提供。
        """
        return pd.DataFrame()

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        """获取实时行情快照

        BaoStock 不提供实时行情，返回空 DataFrame。
        实时行情由 AkShareSource.get_realtime_quotes() 提供。
        """
        return pd.DataFrame()

    def get_stock_metrics(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取预筛指标（BaoStock 部分）

        从 BaoStock 的财报和基础信息接口获取指标：
        - name, list_date: query_stock_basic
        - industry: query_stock_industry
        - ROE: query_profit_data → roeAvg × 100
        - debt_ratio: query_balance_data → liabilityToAsset × 100
        - revenue: query_profit_data → netProfit / npMargin（估算营业收入）

        BaoStock 的财报接口逐只查询，300 只大约需要 2-3 分钟。
        请求间隔由 MetricsSyncer 在外层控制。
        """
        self._ensure_login()

        # 确定最新财报季度
        now = pd.Timestamp.now()
        year = now.year
        quarter = max(1, (now.month - 1) // 3)
        # 如果是年初，可能还没有一季报，回退到去年四季度
        if now.month <= 4:
            year -= 1
            quarter = 4

        results = []
        for symbol in symbols:
            try:
                bs_code = self._to_baostock_code(symbol)
                row = {"symbol": symbol}

                # 基础信息：名称、上市日期
                rs = bs.query_stock_basic(code=bs_code)
                if rs.error_code == "0" and rs.next():
                    data = rs.get_row_data()
                    row["name"] = data[1]  # code_name
                    row["list_date"] = data[2]  # ipoDate

                # 行业分类
                rs = bs.query_stock_industry(code=bs_code)
                if rs.error_code == "0" and rs.next():
                    row["industry"] = rs.get_row_data()[3]  # industry

                # 利润表：ROE、净利润、净利润率 → 估算营收
                rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0" and rs.next():
                    data = rs.get_row_data()
                    fields = rs.fields
                    d = dict(zip(fields, data))
                    roe = d.get("roeAvg")
                    row["roe"] = float(roe) * 100 if roe else None
                    np_margin = d.get("npMargin")
                    net_profit = d.get("netProfit")
                    if np_margin and net_profit and float(np_margin) > 0:
                        row["revenue"] = float(net_profit) / float(np_margin) / 1e8

                # 资产负债表：资产负债率
                rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0" and rs.next():
                    d = dict(zip(rs.fields, rs.get_row_data()))
                    ratio = d.get("liabilityToAsset")
                    row["debt_ratio"] = float(ratio) * 100 if ratio else None

                results.append(row)
            except Exception:
                results.append({"symbol": symbol})

        df = pd.DataFrame(results)
        # 补齐 stock_metrics 表所需的全部列
        for col in ["name", "industry", "list_date", "market_cap", "pe", "pb",
                     "roe", "debt_ratio", "revenue", "operating_cashflow"]:
            if col not in df.columns:
                df[col] = None
        return df

    def __del__(self):
        """析构时自动登出 BaoStock 服务，释放服务端资源"""
        if self._logged_in:
            bs.logout()
