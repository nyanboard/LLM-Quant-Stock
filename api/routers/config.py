"""
配置管理 API
"""
from fastapi import APIRouter

router = APIRouter(tags=["config"])


@router.get("/config/quant-rules")
async def get_quant_rules():
    """获取量化筛选规则"""
    # TODO: 读取 config/quant_rules.yaml
    pass


@router.put("/config/quant-rules")
async def update_quant_rules():
    """更新量化筛选规则"""
    # TODO: 更新并重新加载
    pass


@router.get("/config/universes")
async def get_universes():
    """获取可选的股票池列表"""
    return {
        "universes": [
            {"id": "hs300", "name": "沪深300"},
            {"id": "zz500", "name": "中证500"},
            {"id": "zz1000", "name": "中证1000"},
            {"id": "sza", "name": "全A"},
        ]
    }
