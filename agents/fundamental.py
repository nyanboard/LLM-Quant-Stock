"""
基本面分析师 Agent
职责：分析财报数据，评估财务健康度、增长性、估值水平
输入：利润表、资产负债表、现金流量表数据
输出：财务健康评分 + 看多/看空理由
"""
from agents.base import BaseAgent, AgentSignal


class FundamentalAgent(BaseAgent):
    name = "fundamental"

    def analyze(self, stock_data: dict) -> AgentSignal:
        # TODO:
        # 1. 提取财报关键指标（营收增速、ROE、负债率、现金流）
        # 2. 构建 LLM prompt，注入财报数据
        # 3. 调用 LLM 获取分析结果
        # 4. 解析输出为 AgentSignal
        raise NotImplementedError
