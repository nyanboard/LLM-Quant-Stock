"""
CLI 入口
"""
import argparse
from config.settings import load_config
from data.baostock_source import BaoStockSource
from data.akshare_source import AkShareSource
from workflow.pipeline import StockSelectionPipeline


def main():
    parser = argparse.ArgumentParser(description="LLM-Quant-Stock AI选股系统")
    parser.add_argument("--universe", default="hs300", choices=["hs300", "zz500", "zz1000", "sza"])
    parser.add_argument("--date", default=None, help="分析日期 YYYY-MM-DD")
    parser.add_argument("--serve", action="store_true", help="启动 API 服务")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
        return

    config = load_config()
    datasource = BaoStockSource()  # 主数据源
    pipeline = StockSelectionPipeline(datasource, config)

    print(f"开始选股：股票池={args.universe}")
    picks = pipeline.run(universe=args.universe, date=args.date)

    print(f"\n选出 {len(picks)} 只股票：")
    for i, stock in enumerate(picks, 1):
        print(f"  {i}. {stock.get('symbol')} {stock.get('name', '')} - 评分: {stock.get('total_score', 0):.1f}")
        print(f"     理由: {stock.get('reasoning', '')}")


if __name__ == "__main__":
    main()
