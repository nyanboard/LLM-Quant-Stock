"""
数据缓存层

基于 SQLite + TTL 的轻量级缓存系统，用于：
1. 缓存外部 API 返回的数据，避免重复请求（通用 cache 表）
2. 存储全量股票指标（stock_metrics 宽表：慢数据 + 实时行情）

所有数据共用同一个 SQLite 数据库文件（data/cache/stock_data.db），
通过不同的表名区分功能，无需额外数据库服务。

设计原则：
- 通用缓存使用 KV 结构（key 为 MD5 哈希），适合缓存任意 API 返回的 DataFrame
- stock_metrics 使用 symbol 做主键，每只股票一条记录，UPSERT 覆盖更新
- 所有时间戳使用 time.time() 返回的 Unix timestamp（浮点数）
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

import pandas as pd


class DataCache:
    """数据缓存管理器，封装所有 SQLite 表的读写操作

    使用方式：
        cache = DataCache("data/cache/stock_data.db")
        cache.init_metrics_table()     # 首次使用时建表

    注意：SQLite 连接不是线程安全的，多线程环境下需要每个线程创建独立实例，
    或使用 check_same_thread=False 参数（不推荐）。
    """

    def __init__(self, db_path: str = "data/cache/stock_data.db"):
        """初始化缓存管理器

        Args:
            db_path: SQLite 数据库文件路径，如果文件不存在会自动创建。
                     目录也会自动创建（如 data/cache/）。
        """
        # 确保数据库目录存在，避免 SQLite 因目录不存在而报错
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        # 使用 Row 工厂，让查询结果可以通过列名访问（如 row["symbol"]），而不是 row[0]
        self._conn.row_factory = sqlite3.Row
        # 自动建通用缓存表（保持向后兼容）
        self._init_table()

    # ══════════════════════════════════════════════════════════════
    # 通用缓存（KV 结构，用于缓存任意 API 返回的 DataFrame）
    # ══════════════════════════════════════════════════════════════

    def _init_table(self):
        """初始化通用缓存表（保持向后兼容，原有逻辑不变）

        表结构：
        - key: MD5 哈希值，由 source + method + params 组合生成，唯一标识一个缓存条目
        - data: JSON 格式的 DataFrame 数据（orient="records"）
        - created_at: 缓存创建时间（Unix timestamp），用于 TTL 过期判断
        """
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

    @staticmethod
    def _make_key(source: str, method: str, params: dict) -> str:
        """生成缓存 key

        将 数据源名称 + 方法名 + 参数 按确定性顺序序列化后取 MD5，
        确保相同的查询参数总是生成相同的 key。

        Args:
            source: 数据源名称，如 "akshare"、"baostock"
            method: 方法名称，如 "get_daily_quotes"
            params: 查询参数字典，会按 key 排序保证序列化确定性

        Returns:
            32 位 MD5 哈希字符串
        """
        raw = f"{source}:{method}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_dataframe(
        self, source: str, method: str, params: dict, ttl: int = 3600
    ) -> Optional[pd.DataFrame]:
        """获取缓存的 DataFrame

        如果缓存不存在或已过期，返回 None，由调用方决定是否重新拉取数据。

        Args:
            source: 数据源名称
            method: 方法名称
            params: 查询参数
            ttl: 缓存有效期（秒），默认 3600 秒（1 小时）

        Returns:
            缓存的 DataFrame，如果过期或不存在则返回 None
        """
        key = self._make_key(source, method, params)
        row = self._conn.execute(
            "SELECT data, created_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        # 缓存不存在，或已超过 TTL 有效期
        if row is None or (time.time() - row[1]) > ttl:
            return None
        return pd.read_json(row[0])

    def set_dataframe(self, source: str, method: str, params: dict, df: pd.DataFrame):
        """将 DataFrame 写入缓存

        使用 INSERT OR REPLACE 策略：如果 key 已存在则覆盖更新。

        Args:
            source: 数据源名称
            method: 方法名称
            params: 查询参数
            df: 要缓存的数据
        """
        key = self._make_key(source, method, params)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, created_at) VALUES (?, ?, ?)",
            (key, df.to_json(orient="records"), time.time()),
        )
        self._conn.commit()

    def clear_expired(self):
        """清理过期的通用缓存条目

        默认清理 7 天前的缓存记录。对于 stock_metrics 等专用表，
        过期判断在各自的 get 方法中通过 TTL 参数完成，无需主动清理。
        """
        cutoff = time.time() - 7 * 86400
        self._conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
        self._conn.commit()

    # ══════════════════════════════════════════════════════════════
    # stock_metrics 表（预筛指标缓存）
    # ══════════════════════════════════════════════════════════════

    def init_metrics_table(self):
        """初始化 stock_metrics 全量宽表

        用于存储每日同步的全部股票指标（慢数据 + 实时行情）。
        每只股票一条记录，以 symbol 为主键。

        表结构与数据来源：
        - symbol: 股票代码（纯数字格式，如 "600519"），PK，统一由数据层转换
        - name: 股票名称（如 "贵州茅台"），来自 akshare
        - industry: 申万行业分类（如 "白酒"），来自 akshare
        - list_date: 上市日期（如 "2001-08-27"），来自 akshare
        - market_cap: 总市值（单位：亿元），来自 akshare
        - pe: 滚动市盈率 TTM，来自 akshare
        - pb: 市净率，来自 akshare
        - roe: 最近一期净资产收益率（%），来自 baostock 财报
        - debt_ratio: 资产负债率（%），来自 baostock 财报
        - revenue: 最近一期营业收入（单位：亿元），来自 baostock 财报
        - operating_cashflow: 最近一期经营活动现金流（单位：亿元），来自 baostock 财报
        - is_st: 是否 ST/*ST（0/1），来自 akshare 实时行情
        - is_suspended: 是否停牌（0/1），来自 akshare 实时行情
        - is_limit_up: 是否涨停（0/1），来自 akshare 实时行情
        - is_limit_down: 是否跌停（0/1），来自 akshare 实时行情
        - price: 最新价格（元），来自 akshare 实时行情
        - turnover_rate: 换手率（%），来自 akshare 实时行情
        - avg_amount: 日均成交额（万元），来自 akshare 实时行情
        - synced_at: 数据同步时间（Unix timestamp），用于 TTL 过期判断
        """
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_metrics (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                list_date TEXT,
                market_cap REAL,
                pe REAL,
                pb REAL,
                roe REAL,
                debt_ratio REAL,
                revenue REAL,
                operating_cashflow REAL,
                is_st INTEGER,
                is_suspended INTEGER,
                is_limit_up INTEGER,
                is_limit_down INTEGER,
                price REAL,
                turnover_rate REAL,
                avg_amount REAL,
                synced_at REAL NOT NULL
            )
        """)
        # 兼容：如果已有旧表缺少实时字段，自动补齐
        self._ensure_realtime_columns()
        self._conn.commit()

    def get_metrics(self, symbols: list[str], ttl: int = 86400) -> Optional[pd.DataFrame]:
        """批量查询预筛指标

        从 stock_metrics 表中查询指定股票的指标数据。
        如果任一条记录的 synced_at 超过 TTL，或者部分股票不在表中，返回 None。
        这种"全有或全无"的策略确保预筛使用的是同一批次同步的数据，避免数据时点不一致。

        Args:
            symbols: 股票代码列表（纯数字格式），如 ["600519", "000858"]
            ttl: 数据有效期（秒），默认 86400（1 天）

        Returns:
            包含所有指定股票指标的 DataFrame，如果数据过期或不完整则返回 None
        """
        if not symbols:
            return None
        placeholders = ",".join("?" * len(symbols))
        rows = self._conn.execute(
            f"SELECT * FROM stock_metrics WHERE symbol IN ({placeholders})", symbols
        ).fetchall()
        if not rows:
            return None
        synced_at = rows[0]["synced_at"]
        # ttl=0 表示不过期检查（用于内部读取最新数据）
        if ttl > 0 and (time.time() - synced_at) > ttl:
            return None
        return pd.DataFrame([dict(r) for r in rows])

    def query_metrics(self, filters: Optional[dict] = None) -> pd.DataFrame:
        """查询 stock_metrics 表，支持动态过滤条件

        Args:
            filters: 过滤条件字典，键为列名，值为 (operator, value) 元组或精确值。
                     示例: {"pe": (">", 5), "is_st": 0, "roe": (">=", 3)}
                     不传则返回全表。

        Returns:
            包含查询结果的 DataFrame
        """
        where_clauses = []
        params = []
        if filters:
            for col, cond in filters.items():
                if isinstance(cond, tuple):
                    op, val = cond
                    where_clauses.append(f"{col} {op} ?")
                    params.append(val)
                else:
                    where_clauses.append(f"{col} = ?")
                    params.append(cond)

        sql = "SELECT * FROM stock_metrics"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        rows = self._conn.execute(sql, params).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def get_sync_status(self) -> dict:
        """获取 stock_metrics 同步状态

        Returns:
            {"status": "idle"/"no_data", "total_count": int, "last_synced_at": float|None}
        """
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt, MAX(synced_at) as latest FROM stock_metrics"
        ).fetchone()
        total = row["cnt"]
        latest = row["latest"]
        return {
            "status": "idle" if total > 0 else "no_data",
            "total_count": total,
            "last_synced_at": latest,
        }

    def _ensure_realtime_columns(self):
        """兼容旧表：检测并补齐实时行情字段（ALTER TABLE ADD COLUMN）"""
        realtime_cols = [
            "is_st", "is_suspended", "is_limit_up", "is_limit_down",
            "price", "turnover_rate", "avg_amount",
        ]
        # 获取现有列名
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(stock_metrics)").fetchall()}
        for col in realtime_cols:
            if col not in existing:
                self._conn.execute(f"ALTER TABLE stock_metrics ADD COLUMN {col} REAL")
                # SQLite 没有 BOOLEAN 类型，用 INTEGER 存储 0/1
                # 但 ALTER TABLE ADD COLUMN 不能改类型，统一用 REAL（Python 中 0/1 也能存）
                # 实际上 SQLite 是动态类型，REAL 列也能存整数，无需特殊处理

    def upsert_metrics(self, df: pd.DataFrame):
        """批量写入/更新指标（合并感知策略）

        对于已存在的 symbol，仅更新 DataFrame 中非 None 的字段，
        保留该 symbol 已有的其他字段值。避免覆盖来自其他数据源的数据。

        Args:
            df: 包含指标数据的 DataFrame，必须包含 symbol 列，可选列：
                name, industry, list_date, market_cap, pe, pb,
                roe, debt_ratio, revenue, operating_cashflow,
                is_st, is_suspended, is_limit_up, is_limit_down,
                price, turnover_rate, avg_amount, synced_at
        """
        metric_cols = [
            "name", "industry", "list_date", "market_cap", "pe", "pb",
            "roe", "debt_ratio", "revenue", "operating_cashflow",
            "is_st", "is_suspended", "is_limit_up", "is_limit_down",
            "price", "turnover_rate", "avg_amount",
            "synced_at",
        ]
        for _, row in df.iterrows():
            symbol = row.get("symbol")
            if not symbol:
                continue

            existing = self._conn.execute(
                "SELECT * FROM stock_metrics WHERE symbol = ?", (symbol,)
            ).fetchone()

            if existing is None:
                values = tuple(row.get(c) for c in ["symbol"] + metric_cols)
                placeholders = ",".join("?" * (1 + len(metric_cols)))
                self._conn.execute(
                    f"INSERT INTO stock_metrics (symbol, {','.join(metric_cols)}) VALUES ({placeholders})",
                    values,
                )
            else:
                updates = {}
                for col in metric_cols:
                    val = row.get(col)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        updates[col] = val
                if updates:
                    set_clause = ", ".join(f"{col} = ?" for col in updates.keys())
                    self._conn.execute(
                        f"UPDATE stock_metrics SET {set_clause} WHERE symbol = ?",
                        list(updates.values()) + [symbol],
                    )
        self._conn.commit()
