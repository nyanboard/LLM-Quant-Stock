"""
情绪分析师 Agent
职责：分析新闻、社交媒体情绪，评估市场对个股的看法
输入：个股新闻、股吧热帖、龙虎榜数据
输出：情绪评分 + 情绪标签
"""
from agents.base import BaseAgent, AgentSignal


class SentimentAgent(BaseAgent):
    name = "sentiment"

    def analyze(self, stock_data: dict) -> AgentSignal:
        # TODO:
        # 1. 提取新闻标题和摘要
        # 2. 构建 LLM prompt，注入新闻文本
        # 3. 调用 LLM 评估情绪
        # 4. 输出 AgentSignal
        raise NotImplementedError
