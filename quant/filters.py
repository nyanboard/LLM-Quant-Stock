"""
筛选规则引擎
根据 YAML 配置的规则对股票进行过滤和评分
"""
import yaml
from pathlib import Path


class FilterEngine:
    def __init__(self, rules_path: str = "config/quant_rules.yaml"):
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, path: str) -> dict:
        p = Path(path)
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8"))
        return {"required": [], "bonus": [], "veto": []}

    def apply(self, stock_metrics: dict) -> dict:
        """应用筛选规则
        Args:
            stock_metrics: {"rsi_14": 45, "macd_golden_cross": True, ...}
        Returns:
            {"passed": bool, "bonus_score": float, "vetoed": bool, "failed_required": [...]}
        """
        result = {"passed": True, "bonus_score": 0, "vetoed": False, "failed_required": []}

        # 一票否决
        for rule in self.rules.get("veto", []):
            if self._eval_condition(rule, stock_metrics):
                result["vetoed"] = True
                result["passed"] = False

        # 必要条件
        for rule in self.rules.get("required", []):
            if not self._eval_condition(rule, stock_metrics):
                result["failed_required"].append(str(rule))
                result["passed"] = False

        # 加分条件
        for rule in self.rules.get("bonus", []):
            if self._eval_condition(rule, stock_metrics):
                result["bonus_score"] += rule.get("score", 0)

        return result

    @staticmethod
    def _eval_condition(rule: dict, metrics: dict) -> bool:
        """评估单条条件，支持简单的字段比较"""
        # TODO: 实现条件解析（支持 rsi_14 < 70, macd_golden_cross: true 等）
        return True
