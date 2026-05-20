"""
Agent 基类
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentSignal:
    """Agent 输出信号统一格式"""
    agent: str              # agent 名称
    symbol: str             # 股票代码
    score: float            # 评分 1-10
    signal: str             # "bullish" / "bearish" / "neutral"
    confidence: float       # 信心度 0-1
    reasoning: str          # 分析理由（中文）
    key_metrics: Optional[dict] = None  # 关键数据指标


class BaseAgent:
    """Agent 基类，所有 Agent 必须继承"""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.llm_model = config.get("llm_model", "deepseek-v3")
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """从 config/prompts/ 加载提示词模板"""
        from pathlib import Path
        prompt_path = Path(f"config/prompts/{self.name}.md")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def analyze(self, stock_data: dict) -> AgentSignal:
        """执行分析，子类必须实现"""
        raise NotImplementedError

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM，子类可覆盖"""
        # TODO: 接入 DeepSeek / Qwen API
        raise NotImplementedError
