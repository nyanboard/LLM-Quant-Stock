"""
新闻分析师 Agent
职责：分析公司公告、行业政策、宏观数据的影响
输入：公司公告、行业政策、宏观数据
输出：政策影响评分 + 关键事件列表
"""
from agents.base import BaseAgent, AgentSignal


class NewsAgent(BaseAgent):
    name = "news"

    def analyze(self, stock_data: dict) -> AgentSignal:
        # TODO:
        # 1. 提取公告和政策文本
        # 2. 构建 LLM prompt，分析对股价的影响
        # 3. 输出 AgentSignal
        raise NotImplementedError
