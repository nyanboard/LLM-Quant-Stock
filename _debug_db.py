"""临时调试脚本 - 检查 DB 数据"""
import sqlite3

db_path = "data/cache/stock_data.db"
conn = sqlite3.connect(db_path)

print("=== stock_metrics ===")
cols = [d[0] for d in conn.execute("SELECT * FROM stock_metrics LIMIT 1").description]
print(f"Columns: {cols}")
count = conn.execute("SELECT COUNT(*) FROM stock_metrics").fetchone()[0]
print(f"Total: {count} rows")

for row in conn.execute("SELECT symbol, name, market_cap, pe, pb, roe FROM stock_metrics LIMIT 5"):
    print(f"  {row}")

for col in ["market_cap", "pe", "pb", "roe"]:
    n = conn.execute(f"SELECT COUNT(*) FROM stock_metrics WHERE {col} IS NOT NULL").fetchone()[0]
    print(f"  {col}: {n}/{count} non-null")

print("\n=== screening_stocks ===")
scount = conn.execute("SELECT COUNT(*) FROM screening_stocks").fetchone()[0]
print(f"Total: {scount} rows")

for row in conn.execute("SELECT symbol, name, passed, market_cap, pe, pb, roe FROM screening_stocks LIMIT 5"):
    print(f"  {row}")

for col in ["market_cap", "pe", "pb", "roe"]:
    n = conn.execute(f"SELECT COUNT(*) FROM screening_stocks WHERE {col} IS NOT NULL").fetchone()[0]
    print(f"  {col}: {n}/{scount} non-null")

conn.close()
