"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import stock, backtest, agent, config as config_router

app = FastAPI(
    title="LLM-Quant-Stock API",
    description="LLM 多Agent选股 + 量化二次筛选系统",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(config_router.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
