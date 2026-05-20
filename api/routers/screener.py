"""
预筛分析 API

提供 4 个端点：
1. POST /screener/run   — 触发预筛（后台执行，返回 screening_id）
2. GET  /screener/result — 获取最近一次（或指定 ID）预筛结果
3. GET  /screener/stats  — 获取预筛统计摘要
4. GET  /screener/history — 获取历史预筛记录列表

设计原则：
- 遵循项目 API 规范：Router 只负责参数接收和返回，不写核心逻辑
- 业务逻辑委托给 data.scheduler 和 data.cache
- POST /run 使用 BackgroundTasks 异步执行预筛，立即返回
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Depends, BackgroundTasks

from api.schemas import (
    ScreenRequest,
    ScreenResultResponse,
    ScreenStatsResponse,
    ScreeningSummary,
    ScreeningStockItem,
)
from data.cache import DataCache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["screener"])


# ── 依赖注入：获取 DataCache 实例 ──
# 通过 FastAPI 的 Depends 机制注入缓存实例，
# 避免在路由中硬编码创建逻辑，方便测试和配置切换。
_cache_instance: Optional[DataCache] = None


def set_cache(cache: DataCache):
    """设置全局缓存实例（由 api/main.py 在启动时调用）

    Args:
        cache: 已初始化的 DataCache 实例（所有表已建好）
    """
    global _cache_instance
    _cache_instance = cache


def get_cache() -> DataCache:
    """FastAPI 依赖注入：获取缓存实例

    Raises:
        HTTPException: 503 如果缓存未初始化
    """
    if _cache_instance is None:
        raise HTTPException(status_code=503, detail="数据缓存未初始化")
    return _cache_instance


def _run_screening_background(universe: str, cache: DataCache):
    """后台任务：执行完整的预筛流程（股票池同步 → 指标同步 → 预筛）"""
    try:
        from data.baostock_source import BaoStockSource
        from data.sync import MetricsSyncer
        from data.scheduler import DataScheduler
        from quant.screener import StockScreener

        datasource = BaoStockSource()
        syncer = MetricsSyncer(datasource=datasource, cache=cache)
        screener = StockScreener(cache=cache)
        scheduler = DataScheduler(
            datasource=datasource,
            cache=cache,
            syncer=syncer,
            screener=screener,
        )
        scheduler.run_daily(universe)
        logger.info("后台预筛完成: universe=%s", universe)
    except Exception:
        logger.exception("后台预筛执行失败")


# ── API 端点 ──

@router.post("/run", response_model=ScreenResultResponse)
async def run_screening(
    req: ScreenRequest,
    background_tasks: BackgroundTasks,
    cache: DataCache = Depends(get_cache),
):
    """触发预筛执行

    后台异步执行：同步股票池 → 同步慢数据 → 执行 8 维度预筛。
    立即返回 status=running，结果通过 GET /result 查询。

    Args:
        req: 预筛请求，包含 universe（股票池标识）

    Returns:
        预筛状态，status=running 表示后台正在执行
    """
    background_tasks.add_task(_run_screening_background, req.universe, cache)
    return ScreenResultResponse(
        screening_id=None,
        universe=req.universe,
        status="running",
        passed=[],
        excluded=[],
        stats=ScreenStatsResponse(
            total=0, passed_count=0, excluded_count=0, dimension_breakdown={},
        ),
    )


@router.get("/result", response_model=ScreenResultResponse)
async def get_screening_result(
    screening_id: Optional[int] = Query(None, description="预筛记录 ID，不传则返回最新"),
    cache: DataCache = Depends(get_cache),
):
    """获取预筛结果

    支持两种查询方式：
    - 不传 screening_id：返回最近一次预筛的完整结果
    - 传入 screening_id：返回指定批次的结果

    Args:
        screening_id: 预筛记录 ID（可选）

    Returns:
        完整的预筛结果（含股票明细）

    Raises:
        HTTPException: 404 如果指定的 screening_id 不存在
    """
    if screening_id is not None:
        result = cache.get_screening(screening_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"预筛记录 {screening_id} 不存在")
    else:
        result = cache.get_latest_screening()
        if result is None:
            raise HTTPException(status_code=404, detail="暂无预筛结果，请先执行预筛")

    # 将 DB 字典转换为响应模型
    stocks = result.get("stocks", [])
    passed = [
        ScreeningStockItem(**s) for s in stocks
        if s.get("passed") == 1
    ]
    excluded = [
        ScreeningStockItem(**s) for s in stocks
        if s.get("passed") == 0
    ]

    return ScreenResultResponse(
        screening_id=result["screening_id"],
        universe=result.get("universe", ""),
        status="completed",
        passed=passed,
        excluded=excluded,
        stats=ScreenStatsResponse(
            total=result["total_count"],
            passed_count=result["passed_count"],
            excluded_count=result["excluded_count"],
            dimension_breakdown=result.get("dimension_breakdown", {}),
        ),
    )


@router.get("/stats", response_model=ScreenStatsResponse)
async def get_screening_stats(cache: DataCache = Depends(get_cache)):
    """获取最近一次预筛的统计摘要

    不返回股票明细，只返回汇总数据。
    适合前端 Dashboard 卡片展示。

    Returns:
        预筛统计：总数、通过数、过滤数、各维度淘汰分布

    Raises:
        HTTPException: 404 如果没有任何预筛结果
    """
    result = cache.get_latest_screening()
    if result is None:
        raise HTTPException(status_code=404, detail="暂无预筛结果")

    return ScreenStatsResponse(
        total=result["total_count"],
        passed_count=result["passed_count"],
        excluded_count=result["excluded_count"],
        dimension_breakdown=result.get("dimension_breakdown", {}),
    )


@router.get("/history", response_model=list[ScreeningSummary])
async def get_screening_history(
    limit: int = Query(10, ge=1, le=50, description="返回记录数量"),
    cache: DataCache = Depends(get_cache),
):
    """获取预筛历史记录列表

    返回最近 N 次预筛的摘要信息（不含股票明细），
    用于前端历史对比和回溯。

    Args:
        limit: 返回记录数量，默认 10，最大 50

    Returns:
        预筛摘要列表，按时间倒序
    """
    screenings = cache.list_screenings(limit=limit)
    return [ScreeningSummary(**s) for s in screenings]
