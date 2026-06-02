"""
数据指标 API

提供 3 个端点：
1. POST /metrics/sync          — 触发全量指标同步（后台执行）
2. GET  /metrics/query         — 查询 stock_metrics 数据（支持动态过滤）
3. GET  /metrics/sync/status    — 获取同步状态

设计原则：
- 遵循项目 API 规范：Router 只负责参数接收和返回，不写核心逻辑
- 业务逻辑委托给 data.scheduler 和 data.cache
- POST /sync 使用 BackgroundTasks 异步执行，立即返回
"""
import logging
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Query, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from data.cache import DataCache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


# ── 依赖注入：获取 DataCache 实例 ──
_cache_instance: Optional[DataCache] = None
_sync_running: bool = False


def set_cache(cache: DataCache):
    """设置全局缓存实例（由 api/__init__.py 在启动时调用）"""
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


CacheDep = Annotated[DataCache, Depends(get_cache)]


# ── Schema 定义 ──

class SyncRequest(BaseModel):
    """同步请求"""
    universe: str = Field(
        default="sza",
        description="股票池标识：hs300/zz500/zz1000/sza（全A）",
    )


class SyncResponse(BaseModel):
    """同步触发响应"""
    sync_id: str = Field(description="同步任务 ID")
    status: str = Field(description="状态：running/completed/failed")
    universe: str = Field(description="股票池标识")


class SyncStatusResponse(BaseModel):
    """同步状态响应"""
    status: str = Field(description="同步状态：idle/running/no_data")
    total_count: int = Field(description="已同步股票数量")
    last_synced_at: Optional[float] = Field(default=None, description="最近同步时间（Unix timestamp）")
    last_synced_at_str: Optional[str] = Field(default=None, description="最近同步时间（可读格式）")


class MetricsItem(BaseModel):
    """单只股票指标"""
    symbol: str
    name: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue: Optional[float] = None
    operating_cashflow: Optional[float] = None
    is_st: Optional[int] = None
    is_suspended: Optional[int] = None
    is_limit_up: Optional[int] = None
    is_limit_down: Optional[int] = None
    price: Optional[float] = None
    turnover_rate: Optional[float] = None
    avg_amount: Optional[float] = None
    synced_at: Optional[float] = None


class MetricsQueryResponse(BaseModel):
    """指标查询响应"""
    total: int = Field(description="查询结果总数")
    items: list[MetricsItem] = Field(description="股票指标列表")


# ── 后台同步任务 ──

def _run_sync_background(universe: str, cache: DataCache):
    """后台任务：执行全量指标同步

    组装数据源和同步器，调用 DataScheduler 执行同步。
    实例化只是组装零件，run_daily 才真正执行并写库。

    Args:
        universe: 股票池标识，如 "hs300"、"sza"（全A）
        cache: SQLite 缓存实例
    """
    global _sync_running
    try:
        _sync_running = True
        from data.baostock_source import BaoStockSource
        from data.akshare_source import AkShareSource
        from data.sync import MetricsSyncer
        from data.scheduler import DataScheduler

        baostock = BaoStockSource()
        akshare = AkShareSource()
        syncer = MetricsSyncer(datasource=baostock, cache=cache, secondary_datasource=akshare)
        scheduler = DataScheduler(
            datasource=baostock,
            cache=cache,
            syncer=syncer,
            realtime_source=akshare,
        )
        scheduler.run_daily(universe)
        logger.info("后台同步完成: universe=%s", universe)
    except Exception:
        logger.exception("后台同步执行失败")
    finally:
        _sync_running = False


# ── API 端点 ──

@router.post("/sync", response_model=SyncResponse, responses={409: {"description": "同步任务正在执行中"}})
async def trigger_sync(
    req: SyncRequest,
    background_tasks: BackgroundTasks,
    cache: CacheDep,
):
    """触发全量指标同步（异步，立即返回）

    后台执行：拉取股票列表 → 同步慢数据 + 实时行情 → 写入 stock_metrics。
    立即返回 status="running"，通过 GET /metrics/sync/status 查询进度。

    Args:
        req: 同步请求，含 universe（股票池标识）
        background_tasks: FastAPI 后台任务管理器
        cache: 依赖注入的 DataCache 实例

    Returns:
        status="running" 的占位响应，前端轮询 GET /sync/status 获取最终结果。
    """
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="同步任务正在执行中，请稍后再试")

    sync_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(_run_sync_background, req.universe, cache)
    return SyncResponse(
        sync_id=sync_id,
        status="running",
        universe=req.universe,
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(cache: CacheDep):
    """获取同步状态

    Returns:
        当前同步状态（idle/running/no_data）、已同步股票数、最近同步时间
    """
    status = cache.get_sync_status()
    last_ts = status["last_synced_at"]
    return SyncStatusResponse(
        status="running" if _sync_running else status["status"],
        total_count=status["total_count"],
        last_synced_at=last_ts,
        last_synced_at_str=datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S") if last_ts else None,
    )


@router.get("/query", response_model=MetricsQueryResponse)
async def query_metrics(
    cache: CacheDep,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
    pe_min: Annotated[Optional[float], Query(description="PE 下限")] = None,
    pe_max: Annotated[Optional[float], Query(description="PE 上限")] = None,
    pb_min: Annotated[Optional[float], Query(description="PB 下限")] = None,
    roe_min: Annotated[Optional[float], Query(description="ROE 下限（%）")] = None,
    market_cap_min: Annotated[Optional[float], Query(description="市值下限（亿元）")] = None,
    market_cap_max: Annotated[Optional[float], Query(description="市值上限（亿元）")] = None,
    is_st: Annotated[Optional[int], Query(description="是否 ST（0=否，1=是）")] = None,
    is_suspended: Annotated[Optional[int], Query(description="是否停牌（0=否，1=是）")] = None,
):
    """查询 stock_metrics 数据，支持动态过滤和分页

    Args:
        cache: 依赖注入的 DataCache 实例
        page: 页码（从 1 开始）
        page_size: 每页条数（最大 100）
        pe_min/pe_max: 市盈率过滤范围
        roe_min: ROE 最低要求
        market_cap_min/max: 市值过滤范围
        is_st: ST 过滤（传 0 排除 ST 股）
        is_suspended: 停牌过滤（传 0 排除停牌股）

    Returns:
        符合条件的股票指标列表（分页）
    """
    filters = {}
    if pe_min is not None:
        filters["pe"] = (">=", pe_min)
    if pe_max is not None:
        filters["pe"] = ("<=", pe_max) if "pe" not in filters else filters["pe"]
    if pb_min is not None:
        filters["pb"] = (">=", pb_min)
    if roe_min is not None:
        filters["roe"] = (">=", roe_min)
    if market_cap_min is not None:
        filters["market_cap"] = (">=", market_cap_min)
    if market_cap_max is not None:
        filters["market_cap"] = ("<=", market_cap_max) if "market_cap" not in filters else filters["market_cap"]
    if is_st is not None:
        filters["is_st"] = is_st
    if is_suspended is not None:
        filters["is_suspended"] = is_suspended

    df = cache.query_metrics(filters if filters else None)
    total = len(df)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end] if not df.empty else df

    items = [MetricsItem(**row.to_dict()) for _, row in page_df.iterrows()]
    return MetricsQueryResponse(total=total, items=items)
