"""
FastAPI 应用入口

路由注册和中间件配置。metrics 路由已注册到 /api/v1/metrics。

启动方式：uvicorn api.main:app --reload --port 8000
注意：uvicorn 查找的是 api.main 模块，本文件实际是 api/__init__.py，
      所以需要创建 api/main.py 作为 re-export 入口。
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import stock, backtest, agent, config as config_router, metrics

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

app = FastAPI(
    title="LLM-Quant-Stock API",
    description="LLM 多Agent选股 + 量化二次筛选",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router, prefix=API_PREFIX)
app.include_router(backtest.router, prefix=API_PREFIX)
app.include_router(agent.router, prefix=API_PREFIX)
app.include_router(config_router.router, prefix=API_PREFIX)
app.include_router(metrics.router, prefix=API_PREFIX)


@app.on_event("startup")
async def startup():
    """应用启动时初始化数据缓存和预筛组件"""
    from data.cache import DataCache

    cache = DataCache()
    cache.init_metrics_table()
    metrics.set_cache(cache)
    logger.info("数据缓存初始化完成，metrics 路由已就绪")
