"""
BaoStock 数据源实现

负责从 BaoStock 获取 A 股的历史数据和财报指标。
在预筛流程中，BaoStockSource 提供：
    - 名称 (name)          ← query_stock_basic
    - 上市日期 (list_date)  ← query_stock_basic
    - 行业 (industry)       ← query_stock_industry
    - ROE (roe)            ← query_profit_data → roeAvg × 100
    - 资产负债率 (debt_ratio) ← query_balance_data → liabilityToAsset × 100
    - 营业收入 (revenue)    ← query_profit_data → netProfit / npMargin（估算）
    - 经营现金流 (operating_cashflow) ← netProfit × CFOToNP（估算）

与 AkShareSource 的分工：
    BaoStock 擅长财报数据（季报/年报），AkShare 擅长实时行情和估值数据。
    两者通过 MetricsSyncer 合并后才能覆盖预筛所需的全部 8 个维度。

BaoStock 特点：
    - 免费开源，专注历史数据和财报
    - 数据稳定，复权数据准确
    - 需要先 login() 才能查询，用完后 logout()
    - 财报接口逐只查询（不支持批量），300 只约需 2-3 分钟
    - 请求频率建议控制在 0.3 秒以上，避免被限流

股票代码格式：
    BaoStock 内部使用带前缀格式：sh.600000（上交所）、sz.000001（深交所）。
    本项目的统一格式是纯数字：600000、000001。
    所有 public 方法接收和返回纯数字格式，内部通过 _to_baostock_code() 转换。

经营现金流估算说明：
    BaoStock 的 query_cash_flow_data() 只返回比率指标（如 CFOToNP），
    不返回经营现金流的绝对金额。因此采用估算公式：
        operating_cashflow = netProfit × CFOToNP
    其中 CFOToNP = 经营活动现金流量净额 / 净利润。
    该估算在大多数情况下误差不超过 5%，满足预筛的精度要求。
"""
import logging

import baostock as bs
import pandas as pd

from data.datasource import DataSource

logger = logging.getLogger(__name__)

# stock_metrics 表所需的全部列（用于补齐缺失列）
_METRIC_COLUMNS = [
    "name", "industry", "list_date", "market_cap", "pe", "pb",
    "roe", "debt_ratio", "revenue", "operating_cashflow",
]


def _parse_baostock_result(rs) -> dict | None:
    """解析 BaoStock 查询结果为字典，失败返回 None

    BaoStock 的查询接口返回统一的 ResultData 对象，需要调用 rs.next()
    获取第一行数据，然后通过 rs.fields 和 rs.get_row_data() 构建字典。

    Args:
        rs: BaoStock 查询返回的 ResultData 对象

    Returns:
        字段名→值的字典，查询失败或无数据时返回 None
    """
    if rs.error_code == "0" and rs.next():
        return dict(zip(rs.fields, rs.get_row_data()))
    return None


class BaoStockSource(DataSource):
    """BaoStock 数据源实现

    使用前需安装：pip install baostock

    BaoStore 使用 login/logout 模式：
    - 首次查询时自动登录（延迟登录，避免不必要的网络连接）
    - 对象销毁时自动登出（释放服务端资源）
    - 避免频繁创建/销毁实例，建议整个流程共用一个实例
    """

    # 指数标识 → BaoStock 查询方法名
    _INDEX_QUERY_MAP = {
        "hs300": "query_hs300_stocks",
        "zz500": "query_zz500_stocks",
        "sz50": "query_sz50_stocks",
    }

    def __init__(self):
        # 延迟登录：只在首次实际查询时登录，不在 __init__ 中登录
        self._logged_in = False

    def _ensure_login(self):
        """确保已登录 BaoStock 服务

        BaoStock 要求在查询数据前先调用 bs.login()。
        采用延迟登录策略，只在首次查询时登录，减少无谓的网络连接。
        """
        if not self._logged_in:
            bs.login()
            self._logged_in = True

    def _to_baostock_code(self, symbol: str) -> str:
        """纯数字格式 → BaoStock 格式

        转换规则：
        - 6 开头 → sh. 前缀（上交所）：600000 → sh.600000
        - 0/3 开头 → sz. 前缀（深交所）：000001 → sz.000001
        - 8 开头 → sz. 前缀（北交所，BaoStock 暂不完全支持）
        """
        prefix = "sh" if symbol.startswith("6") else "sz"
        return f"{prefix}.{symbol}"

    @staticmethod
    def _to_pure_code(baostock_code: str) -> str:
        """BaoStock 格式 → 纯数字格式

        sh.600519 → 600519
        """
        return baostock_code.split(".")[-1]

    # ── 指数成分股 ───────────────────────────────────────────

    def get_stock_list(self, index: str) -> list[str]:
        """获取指数成分股列表

        Args:
            index: 指数标识。"hs300" 沪深300 / "zz500" 中证500 /
                   "sz50" 上证50 / "sza" 全 A 股

        Returns:
            成分股代码列表（纯数字格式），如 ["600519", "000858", ...]
        """
        self._ensure_login()

        if index == "sza":
            return self._get_all_a_stocks()

        method_name = self._INDEX_QUERY_MAP.get(index)
        if method_name is None:
            raise ValueError(
                f"不支持的指数: {index}，支持: {list(self._INDEX_QUERY_MAP.keys())}, sza"
            )

        query_fn = getattr(bs, method_name)
        rs = query_fn()
        stocks = []
        while rs.error_code == "0" and rs.next():
            stocks.append(self._to_pure_code(rs.get_row_data()[1]))
        return stocks

    def _get_all_a_stocks(self) -> list[str]:
        """获取全部 A 股股票代码

        通过 query_all_stock 获取当日所有证券，过滤出 A 股代码。
        A 股特征：上交所 6 开头，深交所 0 或 3 开头。
        """
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        rs = bs.query_all_stock(day=today)
        stocks = []
        while rs.error_code == "0" and rs.next():
            code = rs.get_row_data()[1]  # code 列，格式 sh.600000
            if code and code.startswith(("sh.6", "sz.0", "sz.3")):
                stocks.append(self._to_pure_code(code))
        return stocks

    # ── 以下方法暂未实现，预筛流程不依赖 ──────────────────────────

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        """获取日K线数据（暂未实现，后续回测模块需要时开发）"""
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        """获取财报数据（暂未实现，已有利润表/资产负债表/现金流量表接口）"""
        raise NotImplementedError

    def get_news(self, symbols, limit=20) -> list[dict]:
        """获取个股新闻。BaoStock 不提供新闻数据，由 AkShareSource 负责。"""
        return []

    def get_money_flow(self, symbol) -> pd.DataFrame:
        """获取资金流向。BaoStock 不提供资金流向数据，由 AkShareSource 负责。"""
        return pd.DataFrame()

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        """获取实时行情。BaoStock 不提供实时行情，由 AkShareSource 负责。"""
        return pd.DataFrame()

    # ── 预筛核心方法 ───────────────────────────────────────────

    def get_stock_metrics(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取预筛指标（BaoStock 部分）

        对每只股票依次调用 4 个 BaoStock 接口获取财报和基础数据：
        1. query_stock_basic  → 名称、上市日期
        2. query_stock_industry → 行业分类
        3. query_profit_data  → ROE、净利润、净利润率（估算营收）
        4. query_balance_data → 资产负债率
        5. query_cash_flow_data → CFOToNP（结合净利润估算经营现金流）

        财报接口逐只查询，300 只约需 2-3 分钟。请求间隔由外层
        MetricsSyncer 控制（默认 0.4 秒）。

        单只股票查询失败时记录警告并跳过，不影响其他股票。
        最后补齐 stock_metrics 表所需的全部列（AkShare 负责的字段设为 None）。

        Args:
            symbols: 股票代码列表（纯数字格式）

        Returns:
            DataFrame，列：symbol, name, industry, list_date, market_cap,
            pe, pb, roe, debt_ratio, revenue, operating_cashflow。
            其中 market_cap/pe/pb 由 AkShareSource 补充，此处设为 None。
        """
        self._ensure_login()

        year, quarter = self._latest_report_period()
        results = []

        for symbol in symbols:
            try:
                row = self._fetch_single_metrics(symbol, year, quarter)
                results.append(row)
            except Exception as e:
                logger.warning("获取 %s 指标失败: %s", symbol, e)
                results.append({"symbol": symbol})

        df = pd.DataFrame(results)
        # 补齐 stock_metrics 表所需的全部列（AkShare 负责的字段在此为 None）
        for col in _METRIC_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df

    def _latest_report_period(self) -> tuple[int, int]:
        """计算最新的财报季度

        A 股财报披露规则：
        - 一季报：4 月底前披露
        - 中报（半年报）：8 月底前披露
        - 三季报：10 月底前披露
        - 年报：次年 4 月底前披露

        因此：
        - 1-4 月：上年年报可能尚未披露完毕，使用上年 Q4
        - 5 月起：使用当年已披露的最新季度

        Returns:
            (year, quarter) 元组，如 (2025, 4)
        """
        now = pd.Timestamp.now()
        year = now.year
        quarter = max(1, (now.month - 1) // 3)
        if now.month <= 4:
            year -= 1
            quarter = 4
        return year, quarter

    def _fetch_single_metrics(
        self, symbol: str, year: int, quarter: int
    ) -> dict:
        """获取单只股票的全部预筛指标

        依次调用 BaoStock 的 4 个接口，将结果汇总到一个字典中。
        任何一个接口失败都不影响其他接口的数据获取。

        Args:
            symbol: 股票代码（纯数字格式）
            year: 财报年份
            quarter: 财报季度 (1-4)

        Returns:
            指标字典，key 为 stock_metrics 表的列名
        """
        bs_code = self._to_baostock_code(symbol)
        row = {"symbol": symbol}

        # 1. 基础信息：名称、上市日期
        rs = bs.query_stock_basic(code=bs_code)
        if rs.error_code == "0" and rs.next():
            data = rs.get_row_data()
            row["name"] = data[1]      # code_name
            row["list_date"] = data[2]  # ipoDate

        # 2. 行业分类
        rs = bs.query_stock_industry(code=bs_code)
        if rs.error_code == "0" and rs.next():
            row["industry"] = rs.get_row_data()[3]  # industry

        # 3. 利润表：ROE、净利润、净利润率
        #    营业收入 = 净利润 / 净利润率（BaoStock 不直接提供营收）
        net_profit = None
        rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
        d = _parse_baostock_result(rs)
        if d:
            roe = d.get("roeAvg")
            row["roe"] = float(roe) * 100 if roe else None

            np_margin = d.get("npMargin")
            net_profit = d.get("netProfit")
            if np_margin and net_profit and float(np_margin) > 0:
                # 净利润(元) / 净利润率 → 营业收入(元) → 转亿元
                row["revenue"] = float(net_profit) / float(np_margin) / 1e8

        # 4. 资产负债表：资产负债率
        rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
        d = _parse_baostock_result(rs)
        if d:
            ratio = d.get("liabilityToAsset")
            row["debt_ratio"] = float(ratio) * 100 if ratio else None

        # 5. 现金流量表：经营现金流（估算）
        #    CFOToNP = 经营活动现金流量净额 / 净利润
        #    operating_cashflow = netProfit × CFOToNP
        rs = bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)
        d = _parse_baostock_result(rs)
        if d:
            cfo_to_np = d.get("CFOToNP")
            if cfo_to_np and net_profit and float(cfo_to_np) != 0:
                row["operating_cashflow"] = float(net_profit) * float(cfo_to_np) / 1e8

        return row

    def __del__(self):
        """析构时自动登出 BaoStock 服务，释放服务端资源"""
        if self._logged_in:
            bs.logout()
