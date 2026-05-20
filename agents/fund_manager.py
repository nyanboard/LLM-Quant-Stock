"""
基金经理 Agent
职责：综合所有分析师信号和辩论结果，输出初选股票名单
输入：分析师信号 + 多空辩论结果
输出：初选名单（5-20只）+ 评分 + 买入理由
"""
from agents.base import BaseAgent, AgentSignal


class FundManagerAgent(BaseAgent):
    name = "fund_manager"

    def decide(self, signals: list[list[AgentSignal]], debate: dict) -> list[dict]:
        """综合决策，输出初选名单
        Args:
            signals: 各分析师的信号列表
            debate: 多空辩论结果
        Returns:
            [{"symbol": "600519", "score": 8.5, "reasoning": "..."}]
        """
        # TODO:
        # 1. 汇总所有信号和辩论结论
        # 2. 构建 LLM prompt（使用 deep_think_llm）
        # 3. 让 LLM 综合判断，输出初选名单
        # 4. 解析为标准格式
        raise NotImplementedError
