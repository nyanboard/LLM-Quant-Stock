"""
预筛核心引擎（StockScreener）

在 LLM Agent 分析之前，用确定性规则快速排除不合格标的。
目标是将 300-500 只候选股缩减到 50-100 只，减少 LLM 调用量 60-80%。

预筛维度（共 8 个，全部可配置）：
1. 上市状态：排除 ST/*ST、停牌、次新股（<250 个交易日）
2. 市值：50亿 ~ 5000亿（可配置）
3. 流动性：日均成交额 > 3000万，换手率 > 0.5%
4. 估值：PE > 0 且 < 100，PB > 0 且 < 20
5. 盈利能力：ROE > 3%，营收为正
6. 财务健康：资产负债率 < 80%，经营现金流为正
7. 价格：股价 > 2元
8. 涨跌停：排除涨停/跌停状态

数据来源：
- 慢数据（市值、PE、ROE 等）：从 SQLite 的 stock_metrics 表读取（由 MetricsSyncer 每日同步）
- 实时数据（ST 状态、停牌、涨跌停、价格、换手率）：通过 realtime_data 参数传入

设计原则：
- 8 个维度独立过滤，互不影响
- 任一维度不满足即淘汰（AND 逻辑）
- 每个维度记录淘汰原因，便于前端展示和规则调优
- 统计各维度淘汰数量，形成 dimension_breakdown
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from data.cache import DataCache

logger = logging.getLogger(__name__)


@dataclass
class ScreenResult:
    """预筛结果数据类

    Attributes:
        passed: 通过预筛的股票列表。支持两种格式：
                - 纯字符串列表：["600519", "000858"]（无指标数据）
                - 字典列表：[{"symbol": "600519", "name": "贵州茅台", "pe": 35, ...}]
        excluded: 被过滤掉的股票列表。每项包含 symbol、name、淘汰原因、指标数据
        stats: 统计信息，包含总数、通过数、过滤数、各维度淘汰分布
    """
    passed: list = field(default_factory=list)
    excluded: list = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {
        "total": 0,
        "passed_count": 0,
        "excluded_count": 0,
        "dimension_breakdown": {},
    })


class StockScreener:
    """预筛引擎

    从 stock_metrics 表读取慢数据指标，按 YAML 配置的 8 个维度逐只过滤。
    实时数据（ST/停牌/涨跌停）通过 screen() 方法的 realtime_data 参数传入。

    使用方式：
        screener = StockScreener(cache=data_cache)
        result = screener.screen(["600519", "000858", "000001"])
        print(result.passed)          # 通过的股票
        print(result.excluded)        # 被过滤的股票（含原因）
        print(result.stats)           # 统计信息

    配置文件：config/quant_rules.yaml 的 pre_screen 段落
    """

    def __init__(
        self,
        cache: DataCache,
        rules_path: str = "config/quant_rules.yaml",
    ):
        """初始化预筛引擎

        Args:
            cache: 数据缓存实例，用于查询 stock_metrics 表获取预筛指标
            rules_path: 预筛规则配置文件路径，默认 config/quant_rules.yaml
        """
        self.cache = cache
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """从 YAML 配置文件加载预筛规则

        读取 config/quant_rules.yaml 的 pre_screen 段落。
        如果文件不存在或段落为空，返回空字典（所有维度默认不启用）。

        Returns:
            pre_screen 段落的配置字典，结构如下：
            {
                "exclude_st": true,
                "exclude_suspended": true,
                "min_list_days": 250,
                "market_cap": {"min": 50, "max": 5000},
                "liquidity": {"min_avg_amount": 3000, "min_turnover_rate": 0.5},
                ...
            }
        """
        p = Path(self.rules_path)
        if not p.exists():
            logger.warning("预筛规则文件不存在: %s，所有维度默认不启用", self.rules_path)
            return {}

        with open(p, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 取 pre_screen 段落，如果不存在则返回空字典
        rules = config.get("pre_screen", {})
        if not rules:
            logger.warning("配置文件中缺少 pre_screen 段落: %s", self.rules_path)
        else:
            logger.info("已加载预筛规则，共 %d 个维度", len(rules))

        return rules

    def screen(
        self,
        symbols: list[str],
        realtime_data: Optional[dict] = None,
    ) -> dict:
        """对股票列表执行预筛

        流程：
        1. 从 stock_metrics 表批量查询所有股票的慢数据指标
        2. 逐只股票依次通过 8 个维度的过滤
        3. 任一维度不满足即标记为淘汰，记录淘汰原因
        4. 汇总统计各维度淘汰数量

        Args:
            symbols: 待筛选的股票代码列表（纯数字格式）
            realtime_data: 实时数据字典（可选），格式：
                {
                    "600519": {
                        "is_st": false,
                        "is_suspended": false,
                        "is_limit_up": false,
                        "is_limit_down": false,
                        "price": 1800.0,
                        "turnover_rate": 0.8,
                        "avg_amount": 50000,
                    },
                    ...
                }
                键为股票代码，值为该股票的实时状态数据。
                如果不传入，ST/停牌/涨跌停/价格/流动性等维度将使用
                stock_metrics 中的数据（可能不是最新的）。

        Returns:
            预筛结果字典（可传给 cache.save_screening_result() 直接持久化）：
            {
                "passed": [...],      # 通过的股票
                "excluded": [...],    # 被过滤的股票（含淘汰原因）
                "stats": {...},       # 统计信息
            }
        """
        logger.info("开始预筛 %d 只股票", len(symbols))
        realtime_data = realtime_data or {}

        # Step 1: 从 stock_metrics 表批量查询慢数据
        metrics_df = self.cache.get_metrics(symbols, ttl=0)  # ttl=0 表示不过期判断，用最新数据
        metrics_map = {}  # symbol → 指标字典
        if metrics_df is not None:
            for _, row in metrics_df.iterrows():
                metrics_map[row["symbol"]] = row.to_dict()

        # Step 2: 逐只过滤
        passed = []
        excluded = []
        # 初始化各维度的淘汰计数器
        dimension_counts = {
            "ST": 0,
            "停牌": 0,
            "次新股": 0,
            "市值": 0,
            "流动性": 0,
            "估值": 0,
            "盈利能力": 0,
            "财务健康": 0,
            "价格": 0,
            "涨跌停": 0,
        }

        for symbol in symbols:
            # 获取该股票的慢数据和实时数据
            m = metrics_map.get(symbol, {})  # stock_metrics 中的数据
            rt = realtime_data.get(symbol, {})  # 实时数据（优先级更高）

            # 如果实时数据中有指标值，优先使用实时值
            # （实时数据更新更及时，如当前价格、换手率等）
            data = {**m, **rt}

            # 依次通过 8 个维度过滤
            reasons = []

            # 维度 1: 上市状态（ST/停牌/次新股）
            reasons.extend(self._filter_status(symbol, data))
            # 维度 2: 市值
            reasons.extend(self._filter_market_cap(symbol, data))
            # 维度 3: 流动性
            reasons.extend(self._filter_liquidity(symbol, data))
            # 维度 4: 估值（PE/PB）
            reasons.extend(self._filter_valuation(symbol, data))
            # 维度 5: 盈利能力（ROE/营收）
            reasons.extend(self._filter_profitability(symbol, data))
            # 维度 6: 财务健康（负债率/现金流）
            reasons.extend(self._filter_financial_health(symbol, data))
            # 维度 7: 价格
            reasons.extend(self._filter_price(symbol, data))
            # 维度 8: 涨跌停
            reasons.extend(self._filter_limit(symbol, data))

            # 统计各维度淘汰数
            if reasons:
                excluded.append({
                    "symbol": symbol,
                    "name": data.get("name", ""),
                    "reasons": reasons,
                    "market_cap": data.get("market_cap"),
                    "pe": data.get("pe"),
                    "pb": data.get("pb"),
                    "roe": data.get("roe"),
                    "price": data.get("price"),
                })
                # 按原因归类计数
                for reason in reasons:
                    for dim_name in dimension_counts:
                        if dim_name in reason:
                            dimension_counts[dim_name] += 1
                            break
            else:
                passed.append({
                    "symbol": symbol,
                    "name": data.get("name", ""),
                    "market_cap": data.get("market_cap"),
                    "pe": data.get("pe"),
                    "pb": data.get("pb"),
                    "roe": data.get("roe"),
                    "price": data.get("price"),
                })

        # Step 3: 汇总统计
        result = {
            "passed": passed,
            "excluded": excluded,
            "stats": {
                "total": len(symbols),
                "passed_count": len(passed),
                "excluded_count": len(excluded),
                "dimension_breakdown": {
                    k: v for k, v in dimension_counts.items() if v > 0
                },
            },
        }

        logger.info(
            "预筛完成: 共 %d 只, 通过 %d 只, 过滤 %d 只",
            result["stats"]["total"],
            result["stats"]["passed_count"],
            result["stats"]["excluded_count"],
        )
        return result

    # ── 8 个维度的过滤方法 ──

    def _filter_status(self, symbol: str, data: dict) -> list[str]:
        """维度 1: 上市状态过滤

        检查三个条件：
        1. ST/*ST 状态：排除被实施特别处理的股票（财务状况异常或存在退市风险）
        2. 停牌状态：排除暂停交易的股票（无法买卖）
        3. 次新股：排除上市时间过短的股票（波动大、数据少）

        数据来源：
        - is_st / is_suspended: 来自实时数据（realtime_data）
        - list_date: 来自 stock_metrics（akshare 同步）

        Args:
            symbol: 股票代码
            data: 合并后的指标数据（慢数据 + 实时数据）

        Returns:
            淘汰原因列表，空列表表示通过
        """
        reasons = []

        # 检查 ST 状态
        if self.rules.get("exclude_st", True) and data.get("is_st"):
            reasons.append("ST/*ST")

        # 检查停牌状态
        if self.rules.get("exclude_suspended", True) and data.get("is_suspended"):
            reasons.append("停牌")

        # 检查上市天数
        min_list_days = self.rules.get("min_list_days", 0)
        if min_list_days > 0:
            list_date = data.get("list_date")
            if list_date:
                # 将上市日期字符串转为交易日数（简化计算：250个交易日 ≈ 1年）
                # 更精确的计算需要交易日历，这里用近似值
                try:
                    from datetime import datetime
                    list_dt = datetime.strptime(str(list_date), "%Y-%m-%d")
                    days_since_list = (datetime.now() - list_dt).days
                    trading_days = days_since_list * 250 // 365  # 近似交易日数
                    if trading_days < min_list_days:
                        reasons.append(f"次新股（上市约{trading_days}个交易日）")
                except (ValueError, TypeError):
                    pass  # 日期格式无法解析时跳过此检查

        return reasons

    def _filter_market_cap(self, symbol: str, data: dict) -> list[str]:
        """维度 2: 市值过滤

        排除市值过小（流动性差、风险高）或过大（弹性不足）的股票。

        配置项：
        - market_cap.min: 最小市值（亿元），默认 50
        - market_cap.max: 最大市值（亿元），默认 5000

        数据来源：stock_metrics.market_cap（来自 akshare 实时行情）
        """
        reasons = []
        cap_rules = self.rules.get("market_cap", {})
        cap = data.get("market_cap")

        if cap is not None:
            min_cap = cap_rules.get("min", 0)
            max_cap = cap_rules.get("max", float("inf"))
            if cap < min_cap:
                reasons.append(f"市值过低（{cap:.0f}亿 < {min_cap}亿）")
            elif cap > max_cap:
                reasons.append(f"市值过高（{cap:.0f}亿 > {max_cap}亿）")

        return reasons

    def _filter_liquidity(self, symbol: str, data: dict) -> list[str]:
        """维度 3: 流动性过滤

        确保股票有足够的交易量和换手率，避免买入后难以卖出。

        配置项：
        - liquidity.min_avg_amount: 日均成交额下限（万元），默认 3000（即 3000 万）
        - liquidity.min_turnover_rate: 换手率下限（%），默认 0.5

        数据来源：实时数据中的 avg_amount 和 turnover_rate
        """
        reasons = []
        liq_rules = self.rules.get("liquidity", {})

        # 检查日均成交额
        min_amount = liq_rules.get("min_avg_amount", 0)
        avg_amount = data.get("avg_amount")
        if avg_amount is not None and min_amount > 0 and avg_amount < min_amount:
            reasons.append(f"成交额不足（{avg_amount:.0f}万 < {min_amount}万）")

        # 检查换手率
        min_turnover = liq_rules.get("min_turnover_rate", 0)
        turnover = data.get("turnover_rate")
        if turnover is not None and min_turnover > 0 and turnover < min_turnover:
            reasons.append(f"换手率过低（{turnover:.2f}% < {min_turnover}%）")

        return reasons

    def _filter_valuation(self, symbol: str, data: dict) -> list[str]:
        """维度 4: 估值过滤（PE/PB）

        排除亏损股（PE<0 或无 PE）和估值过高（泡沫）的股票。

        配置项：
        - valuation.pe_min: PE 下限，默认 0（排除亏损股）
        - valuation.pe_max: PE 上限，默认 100（排除泡沫）
        - valuation.pb_min: PB 下限，默认 0
        - valuation.pb_max: PB 上限，默认 20

        数据来源：stock_metrics.pe / stock_metrics.pb（来自 akshare）
        """
        reasons = []
        val_rules = self.rules.get("valuation", {})

        # 检查 PE
        pe = data.get("pe")
        pe_min = val_rules.get("pe_min", None)
        pe_max = val_rules.get("pe_max", None)
        if pe is not None:
            if pe_min is not None and pe < pe_min:
                reasons.append(f"PE过低（{pe:.1f} < {pe_min}）")
            if pe_max is not None and pe > pe_max:
                reasons.append(f"PE过高（{pe:.1f} > {pe_max}）")

        # 检查 PB
        pb = data.get("pb")
        pb_min = val_rules.get("pb_min", None)
        pb_max = val_rules.get("pb_max", None)
        if pb is not None:
            if pb_min is not None and pb < pb_min:
                reasons.append(f"PB过低（{pb:.2f} < {pb_min}）")
            if pb_max is not None and pb > pb_max:
                reasons.append(f"PB过高（{pb:.2f} > {pb_max}）")

        return reasons

    def _filter_profitability(self, symbol: str, data: dict) -> list[str]:
        """维度 5: 盈利能力过滤

        确保公司有基本的赚钱能力。

        配置项：
        - profitability.min_roe: ROE 下限（%），默认 3
        - profitability.revenue_positive: 是否要求营收为正，默认 true

        数据来源：stock_metrics.roe / stock_metrics.revenue（来自 baostock 财报）
        """
        reasons = []
        prof_rules = self.rules.get("profitability", {})

        # 检查 ROE
        min_roe = prof_rules.get("min_roe", 0)
        roe = data.get("roe")
        if roe is not None and min_roe > 0 and roe < min_roe:
            reasons.append(f"ROE不足（{roe:.1f}% < {min_roe}%）")

        # 检查营收是否为正
        if prof_rules.get("revenue_positive", False):
            revenue = data.get("revenue")
            if revenue is not None and revenue <= 0:
                reasons.append(f"营收为负（{revenue:.1f}亿）")

        return reasons

    def _filter_financial_health(self, symbol: str, data: dict) -> list[str]:
        """维度 6: 财务健康过滤

        排除高负债或造血能力差的公司。

        配置项：
        - financial_health.max_debt_ratio: 资产负债率上限（%），默认 80
        - financial_health.operating_cashflow_positive: 是否要求经营现金流为正，默认 true

        数据来源：stock_metrics.debt_ratio / stock_metrics.operating_cashflow（来自 baostock）
        """
        reasons = []
        health_rules = self.rules.get("financial_health", {})

        # 检查资产负债率
        max_debt = health_rules.get("max_debt_ratio", 100)
        debt_ratio = data.get("debt_ratio")
        if debt_ratio is not None and debt_ratio > max_debt:
            reasons.append(f"负债率过高（{debt_ratio:.1f}% > {max_debt}%）")

        # 检查经营现金流
        if health_rules.get("operating_cashflow_positive", False):
            cashflow = data.get("operating_cashflow")
            if cashflow is not None and cashflow <= 0:
                reasons.append(f"经营现金流为负（{cashflow:.1f}亿）")

        return reasons

    def _filter_price(self, symbol: str, data: dict) -> list[str]:
        """维度 7: 价格过滤

        排除低价股（通常风险较高，可能面临退市）。

        配置项：
        - price.min: 最低价格（元），默认 2

        数据来源：实时数据中的 price，或 stock_metrics 表
        """
        reasons = []
        price_rules = self.rules.get("price", {})
        min_price = price_rules.get("min", 0)

        if min_price > 0:
            price = data.get("price")
            if price is not None and price < min_price:
                reasons.append(f"价格过低（{price:.2f}元 < {min_price}元）")

        return reasons

    def _filter_limit(self, symbol: str, data: dict) -> list[str]:
        """维度 8: 涨跌停过滤

        排除涨停（追涨风险大，买不进去）和跌停（恐慌出逃，卖不出去）的股票。

        配置项：
        - exclude_limit_up: 是否排除涨停，默认 true
        - exclude_limit_down: 是否排除跌停，默认 true

        数据来源：实时数据中的 is_limit_up / is_limit_down
        """
        reasons = []

        if self.rules.get("exclude_limit_up", True) and data.get("is_limit_up"):
            reasons.append("涨停")

        if self.rules.get("exclude_limit_down", True) and data.get("is_limit_down"):
            reasons.append("跌停")

        return reasons
