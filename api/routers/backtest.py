"""
回测 API
"""
import uuid
from fastapi import APIRouter
from api.schemas import BacktestRequest, BacktestResponse

router = APIRouter(tags=["backtest"])


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """触发回测"""
    task_id = str(uuid.uuid4())
    # TODO: 调用 backtest 引擎
    return BacktestResponse(
        task_id=task_id,
        status="running",
        metrics={},
        equity_curve=[],
    )


@router.get("/backtest/{task_id}", response_model=BacktestResponse)
async def get_backtest_result(task_id: str):
    """获取回测结果"""
    # TODO: 查询回测结果
    pass
