"""
数据缓存层
基于 SQLite + TTL 的轻量缓存，避免重复请求外部 API
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

import pandas as pd


class DataCache:
    def __init__(self, db_path: str = "data/cache/stock_data.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

    @staticmethod
    def _make_key(source: str, method: str, params: dict) -> str:
        raw = f"{source}:{method}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_dataframe(self, source: str, method: str, params: dict, ttl: int = 3600) -> pd.DataFrame | None:
        """获取缓存的 DataFrame，过期返回 None"""
        key = self._make_key(source, method, params)
        row = self._conn.execute("SELECT data, created_at FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None or (time.time() - row[1]) > ttl:
            return None
        return pd.read_json(row[0])

    def set_dataframe(self, source: str, method: str, params: dict, df: pd.DataFrame):
        """缓存 DataFrame"""
        key = self._make_key(source, method, params)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, created_at) VALUES (?, ?, ?)",
            (key, df.to_json(orient="records"), time.time()),
        )
        self._conn.commit()

    def clear_expired(self):
        """清理过期缓存"""
        # 默认保留 7 天
        cutoff = time.time() - 7 * 86400
        self._conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
        self._conn.commit()
