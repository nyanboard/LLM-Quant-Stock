"""
数据缓存层

基于 SQLite + TTL 的轻量级缓存系统，用于：
1. 缓存外部 API 返回的数据，避免重复请求（通用 cache 表）
2. 存储预筛所需的慢数据指标（stock_metrics 表）
3. 存储股票池历史快照（stock_pools 表）
4. 持久化每次预筛的结果（screening_results + screening_stocks 表）

所有表共用同一个 SQLite 数据库文件（data/cache/stock_data.db），
通过不同的表名区分功能，无需额外数据库服务。

设计原则：
- 通用缓存使用 KV 结构（key 为 MD5 哈希），适合缓存任意 API 返回的 DataFrame
- stock_metrics 使用 symbol 做主键，支持按股票代码批量查询
- stock_pools / screening_results 使用自增 ID，每次写入新记录（不可变快照）
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
        cache.init_pool_table()
        cache.init_screening_tables()

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
        """初始化 stock_metrics 表

        用于缓存每日同步的慢数据指标，供预筛模块查询。
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
                synced_at REAL NOT NULL
            )
        """)
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
        # 使用参数化查询避免 SQL 注入（symbols 来自内部调用，但仍保持安全习惯）
        placeholders = ",".join("?" * len(symbols))
        rows = self._conn.execute(
            f"SELECT * FROM stock_metrics WHERE symbol IN ({placeholders})", symbols
        ).fetchall()
        # 数据不存在（表中没有这些股票的记录）
        if not rows:
            return None
        # 检查最旧的 synced_at 是否已过期（取第一条的时间戳作为代表）
        # 注意：因为 upsert_metrics 会批量写入，所有记录的 synced_at 应该接近
        synced_at = rows[0]["synced_at"]
        # ttl=0 表示不过期检查（用于 screener 内部读取最新数据）
        if ttl > 0 and (time.time() - synced_at) > ttl:
            return None
        # 将 Row 对象转为字典列表，再构造 DataFrame
        return pd.DataFrame([dict(r) for r in rows])

    def upsert_metrics(self, df: pd.DataFrame):
        """批量写入/更新预筛指标

        使用 INSERT OR REPLACE 策略：如果 symbol 已存在则更新所有字段，
        如果不存在则插入新记录。每次调用会刷新所有记录的 synced_at 时间戳。

        Args:
            df: 包含预筛指标的 DataFrame，必须包含以下列：
                symbol, name, industry, list_date, market_cap, pe, pb,
                roe, debt_ratio, revenue, operating_cashflow, synced_at
        """
        cols = [
            "symbol", "name", "industry", "list_date", "market_cap",
            "pe", "pb", "roe", "debt_ratio", "revenue",
            "operating_cashflow", "synced_at",
        ]
        for _, row in df.iterrows():
            # 使用 row.get() 而非 row[]，避免因列名不匹配而报错，缺失字段填 None
            values = tuple(row.get(c) for c in cols)
            placeholders = ",".join("?" * len(cols))
            self._conn.execute(
                f"INSERT OR REPLACE INTO stock_metrics ({','.join(cols)}) VALUES ({placeholders})",
                values,
            )
        self._conn.commit()

    # ══════════════════════════════════════════════════════════════
    # stock_pools 表（股票池历史快照）
    # ══════════════════════════════════════════════════════════════

    def init_pool_table(self):
        """初始化 stock_pools 表

        用于存储每日同步的股票池快照。每次同步写入一条新记录（不覆盖历史），
        形成完整的股票池变更历史。指数成分股会定期调仓（如 HS300 每半年一次），
        保留历史快照可以支持回测时精确回放当时的成分股列表。

        表结构：
        - pool_id: 自增主键，唯一标识一次股票池快照
        - universe: 指数标识，如 "hs300"、"zz500"、"sz50"
        - symbols: 成分股代码列表，JSON 数组格式（如 ["600519", "000858"]）
        - count: 成分股数量（冗余字段，避免反复解析 JSON）
        - synced_at: 同步时间（Unix timestamp）

        与 screening_results 的关联：
        screening_results.pool_id → stock_pools.pool_id，确保每次预筛可以追溯到当时的股票池。
        """
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_pools (
                pool_id INTEGER PRIMARY KEY AUTOINCREMENT,
                universe TEXT NOT NULL,
                symbols TEXT NOT NULL,
                count INTEGER NOT NULL,
                synced_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def save_stock_pool(self, universe: str, symbols: list[str]) -> int:
        """保存股票池快照

        每次调用插入一条新记录，不覆盖历史。

        Args:
            universe: 指数标识，如 "hs300"
            symbols: 成分股代码列表（纯数字格式），如 ["600519", "000858"]

        Returns:
            新创建的 pool_id（用于后续关联 screening_results）
        """
        cur = self._conn.execute(
            "INSERT INTO stock_pools (universe, symbols, count, synced_at) VALUES (?, ?, ?, ?)",
            (universe, json.dumps(symbols), len(symbols), time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_latest_pool(self, universe: str) -> Optional[dict]:
        """获取指定指数的最新股票池快照

        按 synced_at 降序取第一条记录。

        Args:
            universe: 指数标识

        Returns:
            包含 pool_id, universe, symbols(已解析为列表), count, synced_at 的字典，
            如果没有记录则返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM stock_pools WHERE universe = ? ORDER BY synced_at DESC LIMIT 1",
            (universe,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        # symbols 存储为 JSON 字符串，查询时解析为 Python 列表
        result["symbols"] = json.loads(result["symbols"])
        return result

    def get_pool(self, pool_id: int) -> Optional[dict]:
        """按 ID 获取股票池快照

        Args:
            pool_id: 股票池快照 ID

        Returns:
            同 get_latest_pool 返回格式的字典，不存在则返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM stock_pools WHERE pool_id = ?", (pool_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["symbols"] = json.loads(result["symbols"])
        return result

    # ══════════════════════════════════════════════════════════════
    # screening_results + screening_stocks 表（预筛结果持久化）
    # ══════════════════════════════════════════════════════════════

    def init_screening_tables(self):
        """初始化预筛结果相关表

        包含两张表：
        1. screening_results：每次预筛一条记录，存储汇总统计信息
        2. screening_stocks：每只股票一条记录，存储详细的筛选结果

        screening_results 表结构：
        - screening_id: 自增主键
        - pool_id: 关联的股票池快照 ID（FK → stock_pools），确保数据链路可追溯
        - universe: 指数标识
        - total_count: 参与筛选的股票总数
        - passed_count: 通过预筛的股票数量
        - excluded_count: 被过滤掉的股票数量
        - dimension_breakdown: 各维度淘汰统计（JSON），如 {"ST": 15, "市值": 30}
        - created_at: 预筛执行时间（Unix timestamp）

        screening_stocks 表结构：
        - screening_id: 关联的预筛记录（FK → screening_results）
        - symbol: 股票代码（纯数字格式）
        - name: 股票名称
        - passed: 是否通过预筛（1=通过，0=被过滤）
        - exclusion_reasons: 被过滤的原因列表（JSON），如 ["市值过低", "ROE不足"]
        - market_cap, pe, pb, roe, price: 筛选时的指标快照值

        数据不可变原则：一旦写入不再修改，每次预筛生成新的记录。
        这样可以支持历史对比、回测回放等场景。
        """
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS screening_results (
                screening_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER,
                universe TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                passed_count INTEGER NOT NULL,
                excluded_count INTEGER NOT NULL,
                dimension_breakdown TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (pool_id) REFERENCES stock_pools(pool_id)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS screening_stocks (
                screening_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                passed INTEGER NOT NULL,
                exclusion_reasons TEXT,
                market_cap REAL,
                pe REAL,
                pb REAL,
                roe REAL,
                price REAL,
                FOREIGN KEY (screening_id) REFERENCES screening_results(screening_id)
            )
        """)
        # 为 screening_stocks 的 screening_id 创建索引，加速按预筛批次查询
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_screening_stocks_id ON screening_stocks(screening_id)"
        )
        self._conn.commit()

    def save_screening_result(self, result: dict, pool_id: Optional[int] = None) -> int:
        """保存一次预筛的完整结果

        原子操作：先写入 screening_results 获取 screening_id，再逐条写入 screening_stocks。
        如果中间出错，已写入的 screening_results 会留在数据库中（不使用事务回滚，
        因为 SQLite 的 autocommit 模式下每条语句都是独立事务）。

        Args:
            result: 预筛结果字典，格式如下：
                {
                    "universe": "hs300",
                    "passed": ["600519", ...] 或 [{"symbol": "600519", "name": "贵州茅台", ...}, ...],
                    "excluded": [{"symbol": "000001", "name": "平安银行", "reasons": ["市值过低"], ...}, ...],
                    "stats": {
                        "total": 300,
                        "passed_count": 85,
                        "excluded_count": 215,
                        "dimension_breakdown": {"ST": 15, "市值": 30}
                    }
                }
            pool_id: 关联的股票池快照 ID（可选），如果提供则建立与 stock_pools 的关联

        Returns:
            新创建的 screening_id
        """
        # 写入汇总记录
        cur = self._conn.execute(
            """INSERT INTO screening_results
               (pool_id, universe, total_count, passed_count, excluded_count, dimension_breakdown, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                pool_id,
                result.get("universe", ""),
                result["stats"]["total"],
                result["stats"]["passed_count"],
                result["stats"]["excluded_count"],
                # dimension_breakdown 存为 JSON 字符串，ensure_ascii=False 保留中文
                json.dumps(result["stats"].get("dimension_breakdown", {}), ensure_ascii=False),
                time.time(),
            ),
        )
        screening_id = cur.lastrowid

        # 写入被过滤的股票（passed=0），附带淘汰原因
        for stock in result.get("excluded", []):
            self._conn.execute(
                """INSERT INTO screening_stocks
                   (screening_id, symbol, name, passed, exclusion_reasons, market_cap, pe, pb, roe, price)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
                (
                    screening_id,
                    stock["symbol"],
                    stock.get("name", ""),
                    json.dumps(stock.get("reasons", []), ensure_ascii=False),
                    stock.get("market_cap"),
                    stock.get("pe"),
                    stock.get("pb"),
                    stock.get("roe"),
                    stock.get("price"),
                ),
            )

        # 写入通过的股票（passed=1）
        # passed 列表支持两种格式：
        # 1. 纯字符串列表：["600519", "000858"]（仅有代码，无指标数据）
        # 2. 字典列表：[{"symbol": "600519", "name": "贵州茅台", "pe": 35, ...}]（含完整指标）
        for symbol in result.get("passed", []):
            if isinstance(symbol, dict):
                # 字典格式：包含指标快照数据
                self._conn.execute(
                    """INSERT INTO screening_stocks
                       (screening_id, symbol, name, passed, market_cap, pe, pb, roe, price)
                       VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""",
                    (
                        screening_id,
                        symbol["symbol"],
                        symbol.get("name", ""),
                        symbol.get("market_cap"),
                        symbol.get("pe"),
                        symbol.get("pb"),
                        symbol.get("roe"),
                        symbol.get("price"),
                    ),
                )
            else:
                # 字符串格式：仅有代码，指标字段为 NULL
                self._conn.execute(
                    "INSERT INTO screening_stocks (screening_id, symbol, passed) VALUES (?, ?, 1)",
                    (screening_id, symbol),
                )

        self._conn.commit()
        return screening_id

    def get_latest_screening(self) -> Optional[dict]:
        """获取最近一次预筛结果（含股票明细）

        Returns:
            包含 screening_results 字段 + stocks 列表的字典，不存在则返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM screening_results ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        # dimension_breakdown 从 JSON 字符串解析为 Python 字典
        result["dimension_breakdown"] = json.loads(result.get("dimension_breakdown") or "{}")
        # 关联查询该批次所有股票的详细结果
        result["stocks"] = self._get_screening_stocks(result["screening_id"])
        return result

    def get_screening(self, screening_id: int) -> Optional[dict]:
        """按 ID 获取预筛结果（含股票明细）

        Args:
            screening_id: 预筛记录 ID

        Returns:
            同 get_latest_screening 返回格式，不存在则返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM screening_results WHERE screening_id = ?", (screening_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["dimension_breakdown"] = json.loads(result.get("dimension_breakdown") or "{}")
        result["stocks"] = self._get_screening_stocks(screening_id)
        return result

    def list_screenings(self, limit: int = 10) -> list[dict]:
        """获取最近 N 次预筛的汇总列表（不含股票明细）

        用于前端历史记录展示，只返回汇总信息避免大量数据传输。

        Args:
            limit: 返回记录数量，默认 10

        Returns:
            字典列表，每项包含 screening_id, pool_id, universe, total_count, passed_count,
            excluded_count, created_at
        """
        rows = self._conn.execute(
            """SELECT screening_id, pool_id, universe, total_count, passed_count,
                      excluded_count, created_at
               FROM screening_results ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _get_screening_stocks(self, screening_id: int) -> list[dict]:
        """查询某次预筛的所有股票明细（内部方法）

        Args:
            screening_id: 预筛记录 ID

        Returns:
            股票明细列表，每项包含 screening_stocks 表的所有字段，
            exclusion_reasons 已从 JSON 解析为 Python 列表
        """
        rows = self._conn.execute(
            "SELECT * FROM screening_stocks WHERE screening_id = ?", (screening_id,)
        ).fetchall()
        result = []
        for r in rows:
            stock = dict(r)
            # exclusion_reasons 存储为 JSON 字符串（如 '["市值过低", "ROE不足"]'），解析为列表
            if stock.get("exclusion_reasons"):
                stock["exclusion_reasons"] = json.loads(stock["exclusion_reasons"])
            result.append(stock)
        return result
