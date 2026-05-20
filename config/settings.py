"""
全局配置管理
"""
import os
from pathlib import Path


def load_config() -> dict:
    """加载全局配置，优先使用环境变量"""
    return {
        # LLM 配置
        "llm_provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "llm_base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        "llm_model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "deep_think_model": os.getenv("DEEP_THINK_MODEL", "deepseek-reasoner"),

        # Agent 配置
        "debate_rounds": 2,
        "max_shortlist": 20,

        # 评分权重
        "score_weights": {
            "llm": 0.40,
            "technical": 0.30,
            "pattern": 0.20,
            "money_flow": 0.10,
        },

        # 数据源
        "primary_source": "baostock",  # 历史数据
        "realtime_source": "akshare",   # 实时数据

        # 回测默认参数
        "initial_cash": 1_000_000,
        "commission_rate": 0.001,
        "slippage": 0.001,
    }


# 提示词模板目录
PROMPTS_DIR = Path("config/prompts")

# 数据缓存目录
CACHE_DIR = Path("data/cache")

# 输出目录
OUTPUT_DIR = Path("output/reports")
