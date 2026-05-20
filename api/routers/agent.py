"""
Agent 分析过程 API + WebSocket
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["agent"])


@router.get("/agent/signals/{task_id}")
async def get_agent_signals(task_id: str):
    """获取某次选股的所有 Agent 信号"""
    # TODO: 返回各 Agent 的分析结果
    pass


@router.websocket("/ws/agent/{task_id}")
async def agent_progress(websocket: WebSocket, task_id: str):
    """WebSocket 实时推送 Agent 分析进度"""
    await websocket.accept()
    try:
        # TODO: 订阅 Pipeline 的分析进度事件
        # 每当一个 Agent 完成分析时，推送:
        # {"agent": "fundamental", "status": "completed", "signal": {...}}
        while True:
            data = await websocket.receive_text()
            # 保持连接
    except WebSocketDisconnect:
        pass
