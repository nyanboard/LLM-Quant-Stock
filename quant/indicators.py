"""
技术指标计算（TA-Lib 封装）
"""
import pandas as pd
import talib


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    return talib.RSI(close, timeperiod=period)


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    return talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)


def calc_ma(close: pd.Series, period: int) -> pd.Series:
    return talib.MA(close, timeperiod=period)


def calc_boll(close: pd.Series, period: int = 20, nbdev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    return talib.BBANDS(close, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, fastk: int = 9, slowk: int = 3, slowd: int = 3) -> tuple[pd.Series, pd.Series, pd.Series]:
    k, d = talib.STOCH(high, low, close, fastk_period=fastk, slowk_period=slowk, slowd_period=slowd)
    j = 3 * k - 2 * d
    return k, d, j


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """量比 = 当日成交量 / 过去N日平均成交量"""
    ma_vol = talib.MA(volume, timeperiod=period)
    return volume / ma_vol


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次性计算所有常用技术指标"""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    df = df.copy()
    df["rsi_14"] = calc_rsi(c)
    macd, macd_signal, macd_hist = calc_macd(c)
    df["macd"] = macd
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist
    df["ma5"] = calc_ma(c, 5)
    df["ma10"] = calc_ma(c, 10)
    df["ma20"] = calc_ma(c, 20)
    df["ma60"] = calc_ma(c, 60)
    upper, middle, lower = calc_boll(c)
    df["boll_upper"] = upper
    df["boll_middle"] = middle
    df["boll_lower"] = lower
    df["volume_ratio"] = calc_volume_ratio(v)

    return df
