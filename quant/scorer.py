"""
综合评分模型
LLM评分 + 技术指标 + 形态信号 + 资金流向 → 最终评分
"""


class Scorer:
    def __init__(self, weights: dict | None = None):
        self.weights = weights or {
            "llm": 0.40,
            "technical": 0.30,
            "pattern": 0.20,
            "money_flow": 0.10,
        }

    def score(self, llm_score: float, tech_score: float, pattern_score: float, flow_score: float) -> float:
        """加权综合评分"""
        return (
            llm_score * self.weights["llm"]
            + tech_score * self.weights["technical"]
            + pattern_score * self.weights["pattern"]
            + flow_score * self.weights["money_flow"]
        )

    def rank(self, stocks: list[dict]) -> list[dict]:
        """按综合评分排序"""
        for s in stocks:
            s["total_score"] = self.score(
                s.get("llm_score", 0),
                s.get("tech_score", 0),
                s.get("pattern_score", 0),
                s.get("flow_score", 0),
            )
        return sorted(stocks, key=lambda x: x["total_score"], reverse=True)
