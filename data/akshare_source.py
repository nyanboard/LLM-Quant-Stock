"""
AkShare 数据源实现

负责从东方财富等公开数据源获取 A 股的实时行情和估值指标。
在预筛流程中，AkShareSource 提供：
    - 市值 (market_cap)     ← stock_zh_a_spot_em → 总市值
    - 市盈率 (pe)           ← stock_zh_a_spot_em → 市盈率-动态
    - 市净率 (pb)           ← stock_zh_a_spot_em → 市净率
    - 实时行情              ← 价格/涨跌停/ST 状态

与 BaoStockSource 的分工：
    AkShare 擅长实时行情和估值数据，BaoStock 擅长财报数据（ROE、负债率等）。
    两者通过 MetricsSyncer 合并后才能覆盖预筛所需的全部 8 个维度。

SSL 兼容策略：
    macOS Homebrew Python 3.13 的 OpenSSL 3.5 与东方财富 push2 CDN 存在
    TLS 兼容问题（UNEXPECTED_EOF_WHILE_READING）。解决方案：
    1. 优先使用 AkShare 标准接口（正常环境下工作）
    2. 失败时自动 fallback 到 curl_cffi + datacenter-web.eastmoney.com
       该接口使用不同的 CDN 节点，不受 push2 TLS 问题影响

股票代码格式：
    AkShare 使用纯数字格式（如 "000001"），与本项目的统一格式一致，无需转换。
"""
import logging
import time

import pandas as pd

from data.datasource import DataSource

logger = logging.getLogger(__name__)

# datacenter-web 接口支持的查询列名映射
_DATACENTER_METRIC_COLS = (
    "SECURITY_CODE,SECURITY_NAME_ABBR,"
    "TOTAL_MARKET_CAP,PE_TTM,PB_MRQ,"
    "CLOSE_PRICE,CHANGE_RATE,TRADE_DATE"
)

_DATACENTER_REALTIME_COLS = (
    "SECURITY_CODE,SECURITY_NAME_ABBR,"
    "CLOSE_PRICE,CHANGE_RATE,TRADE_DATE"
)


def _fetch_datacenter(symbols: list[str], columns: str, batch_size: int = 200) -> pd.DataFrame:
    """通过东方财富 datacenter-web 接口获取股票数据（curl_cffi fallback）

    当 AkShare 的 stock_zh_a_spot_em() 因 SSL 问题不可用时，
    通过 datacenter-web.eastmoney.com 的 RPT_VALUEANALYSIS_DET 报表获取数据。
    该接口使用不同的 CDN，不受 push2 子域名的 TLS 兼容问题影响。

    使用 curl_cffi 并设置 impersonate="chrome120" 模拟 Chrome 浏览器的
    TLS 指纹，避免被东方财富的反爬系统识别为自动化请求。

    Args:
        symbols: 股票代码列表（纯数字格式）
        columns: 需要查询的列名，逗号分隔
        batch_size: 每批请求的股票数量，默认 200

    Returns:
        DataFrame，按 SECURITY_CODE 分组取最新 TRADE_DATE 的数据。
        如果所有批次均失败，返回空 DataFrame。
    """
    from curl_cffi import requests as curl_requests

    all_dfs = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        filter_str = "(SECURITY_CODE in (" + ",".join(f'"{c}"' for c in batch) + "))"
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get"
            "?reportName=RPT_VALUEANALYSIS_DET"
            f"&columns={columns}"
            f"&filter={filter_str}"
            "&pageSize=500"
            "&sortColumns=TRADE_DATE&sortTypes=-1"
        )

        try:
            r = curl_requests.get(url, impersonate="chrome120", timeout=30)
            data = r.json()
        except Exception as e:
            logger.warning("datacenter 批次 %d 请求失败: %s", i // batch_size, e)
            continue

        if not data.get("result") or not data["result"].get("data"):
            logger.warning("datacenter 批次 %d 无数据", i // batch_size)
            continue

        df_batch = pd.DataFrame(data["result"]["data"])
        # datacenter 返回多日历史数据，按股票代码取最新一天
        df_batch = (
            df_batch.sort_values("TRADE_DATE")
            .groupby("SECURITY_CODE")
            .last()
            .reset_index()
        )
        all_dfs.append(df_batch)

        # 批次间限流，避免触发反爬
        if i + batch_size < len(symbols):
            time.sleep(0.5)

    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


class AkShareSource(DataSource):
    """AkShare 数据源实现

    优先使用 AkShare 标准接口，SSL 不可用时自动 fallback 到 curl_cffi。
    使用前需安装：pip install akshare curl-cffi
    """

    # 指数代码映射：项目标识 → 中证指数代码（供 index_stock_cons_csindex 使用）
    _INDEX_MAP = {
        "hs300": "000300",
        "zz500": "000905",
        "zz1000": "000852",
        "sz50": "000016",
    }

    def __init__(self):
        pass

    def get_stock_list(self, index: str) -> list[str]:
        """获取指数成分股列表

        通过中证指数公司公布的数据获取成分股，准确性高、更新及时。

        Args:
            index: 指数标识。"hs300" 沪深300 / "zz500" 中证500 /
                   "zz1000" 中证1000 / "sz50" 上证50 / "sza" 全 A 股

        Returns:
            成分股代码列表（纯数字格式），如 ["600519", "000858", ...]
        """
        import akshare as ak

        if index == "sza":
            # 全 A 股：从实时行情接口获取所有上市股票代码
            df = ak.stock_zh_a_spot_em()
            return df["代码"].tolist()

        csindex_code = self._INDEX_MAP.get(index)
        if csindex_code is None:
            raise ValueError(f"不支持的指数: {index}，支持: {list(self._INDEX_MAP.keys())}, sza")

        df = ak.index_stock_cons_csindex(symbol=csindex_code)
        return df["成分券代码"].tolist()

    # ── 以下方法暂未实现，预筛流程不依赖 ──────────────────────────

    def get_daily_quotes(self, symbol, start_date=None, end_date=None, adjust="qfq") -> pd.DataFrame:
        """获取日K线数据（暂未实现，后续回测模块需要时开发）"""
        raise NotImplementedError

    def get_financial_report(self, symbol, report_type="income", period=None) -> dict:
        """获取财报数据（暂未实现，AkShare 的财报接口在 stock_financial_* 系列）"""
        raise NotImplementedError

    def get_news(self, symbol, limit=20) -> list[dict]:
        """获取个股新闻（暂未实现，可使用 stock_news_em 接口）"""
        raise NotImplementedError

    def get_money_flow(self, symbol) -> pd.DataFrame:
        """获取资金流向数据（暂未实现，可使用 stock_individual_fund_flow 接口）"""
        raise NotImplementedError

    # ── 预筛核心方法 ───────────────────────────────────────────

    def get_realtime_quotes(self, symbols) -> pd.DataFrame:
        """获取实时行情快照

        返回预筛所需的实时字段：ST 状态、停牌、涨跌停、价格、换手率、成交额。

        获取策略：
        1. 优先使用 AkShare 的 stock_zh_a_spot_em()（数据最全，含换手率和成交额）
        2. 若因 SSL 失败，fallback 到 datacenter-web 获取价格和涨跌幅
           （fallback 模式下换手率和成交额不可用，设为 None）

        Args:
            symbols: 股票代码列表（纯数字格式）

        Returns:
            DataFrame 包含: symbol, is_st, is_suspended, is_limit_up,
            is_limit_down, price, turnover_rate, avg_amount
        """
        # 策略 1：AkShare 标准接口
        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()
            df = df[df["代码"].isin(symbols)]
            change_pct = df.get("涨跌幅", pd.Series(dtype=float))

            return pd.DataFrame({
                "symbol": df["代码"],
                # ST 股票名称中包含 "ST" 或 "*ST"
                "is_st": df["名称"].str.contains("ST", case=False, na=False),
                # 成交量为 0 视为停牌
                "is_suspended": df.get("成交量", pd.Series(0)).fillna(0) == 0,
                # 涨跌幅 >= 9.8% 视为涨停（考虑四舍五入误差，阈值取 9.8 而非 10）
                "is_limit_up": change_pct >= 9.8,
                "is_limit_down": change_pct <= -9.8,
                "price": df["最新价"],
                "turnover_rate": df["换手率"],
                # 成交额从元转为万元
                "avg_amount": df["成交额"] / 1e4,
            })
        except Exception as e:
            logger.warning("AkShare 实时行情失败，使用 datacenter fallback: %s", str(e))

        # 策略 2：curl_cffi + datacenter-web fallback
        try:
            df = _fetch_datacenter(symbols, _DATACENTER_REALTIME_COLS)
            if df.empty:
                return pd.DataFrame()

            change_rate = df["CHANGE_RATE"]
            names = df["SECURITY_NAME_ABBR"]

            return pd.DataFrame({
                "symbol": df["SECURITY_CODE"],
                "is_st": names.str.contains("ST", case=False, na=False),
                # datacenter 无法判断停牌，默认 False（停牌股通常不在指数成分中）
                "is_suspended": False,
                "is_limit_up": change_rate >= 9.8,
                "is_limit_down": change_rate <= -9.8,
                "price": df["CLOSE_PRICE"],
                # datacenter 不提供换手率和成交额
                "turnover_rate": None,
                "avg_amount": None,
            })
        except Exception as e2:
            logger.warning("datacenter 实时行情也失败: %s", str(e2))
            return pd.DataFrame()

    def get_stock_metrics(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取预筛指标（AkShare 部分）

        从东方财富获取全市场行情，提取市值、PE、PB 等估值指标。
        一次 API 调用即可获取全部约 5000 只 A 股的数据，效率较高。

        AkShare 不提供 ROE、负债率、现金流等财报指标，
        这些由 BaoStockSource.get_stock_metrics() 补充。
        两个数据源的结果由 MetricsSyncer._merge_metrics() 合并。

        获取策略：
        1. 优先使用 AkShare 的 stock_zh_a_spot_em()
        2. 若因 SSL 失败，fallback 到 datacenter-web 接口

        Args:
            symbols: 股票代码列表（纯数字格式）

        Returns:
            DataFrame，列：symbol, name, industry, list_date, market_cap,
            pe, pb, roe, debt_ratio, revenue, operating_cashflow, synced_at
            其中 AkShare 只填充 name/market_cap/pe/pb/synced_at，
            其余列设为 None，由 BaoStockSource 补充。
        """
        # AkShare 提供的指标模板（非 AkShare 提供的字段设为 None）
        none_fields = {
            "industry": None,
            "list_date": None,
            "roe": None,
            "debt_ratio": None,
            "revenue": None,
            "operating_cashflow": None,
        }

        # 策略 1：AkShare 标准接口
        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()
            df = df[df["代码"].isin(symbols)]

            result = pd.DataFrame({
                "symbol": df["代码"],
                "name": df["名称"],
                # 总市值从元转为亿元
                "market_cap": df["总市值"] / 1e8,
                "pe": df["市盈率-动态"],
                "pb": df["市净率"],
                "synced_at": time.time(),
            })
            for col, val in none_fields.items():
                result[col] = val
            return result
        except Exception as e:
            logger.warning("AkShare 指标获取失败，使用 datacenter fallback: %s", str(e))

        # 策略 2：curl_cffi + datacenter-web fallback
        try:
            df = _fetch_datacenter(symbols, _DATACENTER_METRIC_COLS)
            if df.empty:
                raise RuntimeError("datacenter 返回空数据")

            result = pd.DataFrame({
                "symbol": df["SECURITY_CODE"],
                "name": df["SECURITY_NAME_ABBR"],
                # 总市值从元转为亿元
                "market_cap": df["TOTAL_MARKET_CAP"] / 1e8,
                "pe": df["PE_TTM"],
                "pb": df["PB_MRQ"],
                "synced_at": time.time(),
            })
            for col, val in none_fields.items():
                result[col] = val
            return result
        except Exception as e2:
            logger.error("所有数据源均不可用: %s", str(e2))
            return pd.DataFrame()
