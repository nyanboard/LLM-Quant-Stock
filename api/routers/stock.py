"""
选股结果 API
"""
import uuid
from fastapi import APIRouter
from api.schemas import (
    SelectionRequest,
    SelectionResponse,
    StockPick,
)

router = APIRouter(tags=["selection"])

# TODO: 替换为真实的任务管理
_tasks: dict[str, SelectionResponse] = {}


@router.post("/selection", response_model=SelectionResponse)
async def run_selection(req: SelectionRequest):
    """触发选股流程"""
    task_id = str(uuid.uuid4())
    # TODO: 调用 workflow/pipeline 执行选股
    return SelectionResponse(
        task_id=task_id,
        status="running",
        universe=req.universe,
        picks=[],
    )


@router.get("/selection/{task_id}", response_model=SelectionResponse)
async def get_selection_result(task_id: str):
    """获取选股结果"""
    # TODO: 查询任务状态和结果
    return _tasks.get(
        task_id,
        SelectionResponse(
            task_id=task_id,
            status="pending",
            universe="",
            picks=[],
        ),
    )


@router.get("/selection/{task_id}/detail/{symbol}", response_model=StockPick)
async def get_stock_detail(task_id: str, symbol: str):
    """获取单只股票的详细分析"""
    # TODO: 返回 Agent 分析详情 + 量化指标
    pass
