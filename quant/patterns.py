"""
K线形态识别
"""
import talib
import pandas as pd


# 常用看涨形态
BULLISH_PATTERNS = [
    "CDLHAMMER",        # 锤子线
    "CDLENGULFING",     # 吞没形态
    "CDLMORNINGSTAR",   # 晨星
    "CDL3WHITESOLDIERS", # 三白兵
    "CDLPIERCING",      # 刺透形态
]

# 常用看跌形态
BEARISH_PATTERNS = [
    "CDLSHOOTINGSTAR",  # 射击之星
    "CDLEVENINGSTAR",   # 暮星
    "CDL3BLACKCROWS",   # 三只乌鸦
    "CDLDARKCLOUDCOVER", # 乌云盖顶
]


def detect_patterns(df: pd.DataFrame) -> list[dict]:
    """识别所有K线形态
    Returns:
        [{"name": "hammer", "type": "bullish", "index": 123}, ...]
    """
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    results = []
    all_patterns = BULLISH_PATTERNS + BEARISH_PATTERNS

    for pattern_name in all_patterns:
        func = getattr(talib, pattern_name, None)
        if func is None:
            continue
        result = func(o, h, l, c)
        # 找到非零位置
        nonzero = result[result != 0]
        for idx, val in nonzero.items():
            pattern_type = "bullish" if pattern_name in BULLISH_PATTERNS else "bearish"
            results.append({
                "name": pattern_name.replace("CDL", "").lower(),
                "type": pattern_type,
                "index": idx,
                "strength": int(val),
            })

    return results


def has_recent_pattern(df: pd.DataFrame, pattern: str, lookback: int = 5) -> bool:
    """检查最近 N 根K线是否出现指定形态"""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    func = getattr(talib, pattern, None)
    if func is None:
        return False
    result = func(o, h, l, c)
    return bool((result.iloc[-lookback:] != 0).any())
