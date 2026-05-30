"""
CLI 入口

支持两种运行模式：
1. 选股模式（默认）：执行预筛 + LLM 分析 + 量化筛选
2. 服务模式（--serve）：启动 FastAPI 后端服务

选股模式参数：
--universe: 股票池选择（hs300/zz500/zz1000/sza）
--date: 分析日期（默认今天）
--skip-screener: 跳过预筛层，直接全量分析（用于调试和对比）
--sync-only: 仅执行数据同步和预筛，不启动 LLM 分析
"""
import argparse
import logging

from config.settings import load_config
from data.baostock_source import BaoStockSource
from data.akshare_source import AkShareSource
from data.cache import DataCache
from data.sync import MetricsSyncer
from data.scheduler import DataScheduler
from quant.screener import StockScreener
from workflow.pipeline import StockSelectionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="LLM-Quant-Stock AI选股系统")
    parser.add_argument("--universe", default="hs300", choices=["hs300", "zz500", "zz1000", "sza"])
    parser.add_argument("--date", default=None, help="分析日期 YYYY-MM-DD")
    parser.add_argument("--skip-screener", action="store_true",
                        help="跳过预筛层，直接全量分析（用于调试和对比）")
    parser.add_argument("--sync-only", action="store_true",
                        help="仅执行数据同步和预筛，不启动 LLM 分析")
    parser.add_argument("--serve", action="store_true", help="启动 API 服务")
    args = parser.parse_args()

    # 服务模式：启动 FastAPI
    if args.serve:
        import uvicorn
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
        return

    # 加载配置和初始化组件
    config = load_config()
    baostock = BaoStockSource()
    akshare = AkShareSource()
    cache = DataCache()
    cache.init_metrics_table()
    cache.init_pool_table()
    cache.init_screening_tables()

    # 仅同步模式：执行每日同步后退出
    if args.sync_only:
        syncer = MetricsSyncer(datasource=baostock, cache=cache, secondary_datasource=akshare)
        screener = StockScreener(cache=cache)
        scheduler = DataScheduler(
            datasource=baostock,
            cache=cache,
            syncer=syncer,
            screener=screener,
            realtime_source=akshare,
        )
        logger.info("执行每日同步（universe=%s）", args.universe)
        result = scheduler.run_daily(args.universe)
        if result:
            print(f"同步完成: pool_id={result['pool_id']}, "
                  f"screening_id={result['screening_id']}, "
                  f"通过预筛 {result['passed_count']}/{result['total_count']} 只")
        else:
            print("同步失败，请检查日志")
        return

    # 选股模式：创建 Pipeline 并执行
    pipeline = StockSelectionPipeline(
        baostock, config, cache=cache,
        secondary_datasource=akshare, realtime_source=akshare,
    )

    mode = "全量分析（跳过预筛）" if args.skip_screener else "预筛 + LLM 分析"
    print(f"开始选股：股票池={args.universe}，模式={mode}")
    picks = pipeline.run(universe=args.universe, date=args.date, skip_screener=args.skip_screener)

    print(f"\n选出 {len(picks)} 只股票：")
    for i, stock in enumerate(picks, 1):
        print(f"  {i}. {stock.get('symbol')} {stock.get('name', '')} - 评分: {stock.get('total_score', 0):.1f}")
        print(f"     理由: {stock.get('reasoning', '')}")


if __name__ == "__main__":
    main()
