"""
多空研究员 Agent
职责：基于分析师报告构建多空论据，进行辩论
输入：基本面/情绪/新闻三个 Analyst 的信号
输出：多空辩论记录 + 共识点/分歧点
"""
from agents.base import BaseAgent, AgentSignal


class ResearcherAgent(BaseAgent):
    name = "researcher"

    def debate(self, signals: list[AgentSignal], rounds: int = 2) -> dict:
        """执行多空辩论
        Args:
            signals: 各分析师的信号
            rounds: 辩论轮次
        Returns:
            {"consensus": [...], "divergence": [...], "bull_args": [...], "bear_args": [...]}
        """
        # TODO:
        # 1. Bull Researcher 构建看多论据
        # 2. Bear Researcher 构建看空论据
        # 3. 交替辩论 rounds 轮
        # 4. 输出共识和分歧
        raise NotImplementedError
