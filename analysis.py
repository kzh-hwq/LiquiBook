"""Lop phan tich: gop theo phut, z-score cuon, canh bao, xep hang thanh khoan, kiem chung.
 
Cong thuc (ghi vao bao cao):
  spread_pct  = (ask1 - bid1) / mid * 100
  imbalance   = (KL mua top3 - KL ban top3) / (KL mua top3 + KL ban top3)   in [-1, 1]
  z-score     = (x_t - mean(x_{t-w..t-1})) / std(x_{t-w..t-1})   (khong dung diem hien tai de tinh nen)
  diem thanh khoan = 100 * sum_i w_i * rank_i, rank_i in [0,1] theo thu hang giua cac ma
                     (spread: thap = tot; do sau va gia tri khop: cao = tot)
"""
from __future__ import annotations
 
import numpy as np
import pandas as pd
 
 
def to_bars(df: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Gop ban ghi theo khung thoi gian cho tung ma."""
    agg = {"mid": "last", "spread_pct": "mean", "bid_depth": "mean", "ask_depth": "mean",
           "depth_value": "mean", "imbalance": "mean", "totalTradingValue": "last",
           "foreignNetValue": "last"}
    agg = {k: v for k, v in agg.items() if k in df.columns}
    bars = (df.set_index("ts").groupby("symbol").resample(freq).agg(agg)
            .dropna(subset=["mid"]).reset_index())
    return bars
 
 
def rolling_z(s: pd.Series, window: int = 30, min_periods: int = 10) -> pd.Series:
    """Z-score so voi cua so w diem TRUOC do. NaN khi chua du du lieu hoac do lech chuan = 0."""
    base = s.shift(1)
    mu = base.rolling(window, min_periods=min_periods).mean()
    sd = base.rolling(window, min_periods=min_periods).std()
    return ((s - mu) / sd).where(sd > 0)
 
 
def add_signals(bars: pd.DataFrame, window: int = 30, min_periods: int = 10,
                z_threshold: float = 2.0) -> pd.DataFrame:
    out = bars.sort_values(["symbol", "ts"]).copy()
    g = out.groupby("symbol")
    out["z_spread"] = g["spread_pct"].transform(lambda s: rolling_z(s, window, min_periods))
    out["z_imbalance"] = g["imbalance"].transform(lambda s: rolling_z(s, window, min_periods))
    out["alert_wide_spread"] = out["z_spread"] >= z_threshold
    out["alert_buy_pressure"] = out["z_imbalance"] >= z_threshold
    out["alert_sell_pressure"] = out["z_imbalance"] <= -z_threshold
    return out
 
 
def _rank_score(s: pd.Series, higher_is_better: bool) -> pd.Series:
    n = s.notna().sum()
    if n <= 1:
        return pd.Series(0.5, index=s.index)
    r = s.rank(ascending=higher_is_better)       # hang 1 = te nhat
    return (r - 1) / (n - 1)
 
 
def liquidity_ranking(bars: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Xep hang thanh khoan giua cac ma. Tra ve bang da sap xep giam dan theo diem (0-100)."""
    w = weights or {"spread": 0.4, "depth": 0.4, "turnover": 0.2}
    stats = bars.groupby("symbol").agg(median_spread_pct=("spread_pct", "median"),
                                       median_depth_value=("depth_value", "median"))
    if "totalTradingValue" in bars.columns:
        day = bars.assign(date=bars["ts"].dt.date).groupby(["symbol", "date"])["totalTradingValue"].max()
        stats["avg_daily_turnover"] = day.groupby("symbol").mean()
    else:
        stats["avg_daily_turnover"] = np.nan
        w = {"spread": 0.5, "depth": 0.5, "turnover": 0.0}
 
    s_spread = _rank_score(stats["median_spread_pct"], higher_is_better=False)
    s_depth = _rank_score(stats["median_depth_value"], higher_is_better=True)
    s_turn = _rank_score(stats["avg_daily_turnover"], higher_is_better=True).where(
        stats["avg_daily_turnover"].notna(), 0.0)
    stats["liquidity_score"] = 100 * (w["spread"] * s_spread + w["depth"] * s_depth + w["turnover"] * s_turn)
    return stats.sort_values("liquidity_score", ascending=False).reset_index()
 
 
def foreign_flow(bars: pd.DataFrame) -> pd.DataFrame:
    """Gia tri mua/ban rong khoi ngoai cuoi moi ngay cho tung ma (lay tu truong luy ke cua API)."""
    if "foreignNetValue" not in bars.columns:
        return pd.DataFrame()
    d = bars.assign(date=bars["ts"].dt.date).sort_values("ts")
    return (d.groupby(["symbol", "date"])["foreignNetValue"].last()
            .rename("foreign_net_value").reset_index())
 
 
def imbalance_vs_forward_return(bars: pd.DataFrame, horizon: int = 5, signal_threshold: float = 0.2) -> dict:
    """Kiem chung: chi so mat can bang co du bao huong gia ngan han khong?
    Tinh tuong quan hang (Spearman) giua imbalance va loi suat `horizon` khung sau (trong cung ngay),
    va ti le dung huong khi |imbalance| >= signal_threshold. Ket qua trung thuc co the la KHONG co quan he."""
    d = bars.sort_values(["symbol", "ts"]).copy()
    d["date"] = d["ts"].dt.date
    d["fwd_ret"] = d.groupby(["symbol", "date"])["mid"].transform(lambda s: s.shift(-horizon) / s - 1)
    d = d.dropna(subset=["imbalance", "fwd_ret"])
    res = {"n": int(len(d)), "horizon_bars": horizon, "spearman": None,
           "hit_rate": None, "n_signals": 0}
    if len(d) < 10:
        return res
    # Spearman = Pearson cua hai chuoi da xep hang (tu tinh, khong can scipy)
    res["spearman"] = float(d["imbalance"].rank().corr(d["fwd_ret"].rank()))
    sig = d[(d["imbalance"].abs() >= signal_threshold) & (d["fwd_ret"] != 0)]
    res["n_signals"] = int(len(sig))
    if len(sig):
        res["hit_rate"] = float((np.sign(sig["imbalance"]) == np.sign(sig["fwd_ret"])).mean())
    return res
 
 
if __name__ == "__main__":
    import sys
    from parse_raw import load_raw, filter_continuous
 
    folder = sys.argv[1] if len(sys.argv) > 1 else "data"
    df = filter_continuous(load_raw(folder))
    if df.empty:
        sys.exit("Khong co du lieu hop le trong phien lien tuc.")
    bars = add_signals(to_bars(df))
    print("\n== Xep hang thanh khoan ==")
    print(liquidity_ranking(bars).round(3).to_string(index=False))
    print("\n== So canh bao ==")
    print(bars.groupby("symbol")[["alert_wide_spread", "alert_buy_pressure", "alert_sell_pressure"]].sum())
    print("\n== Kiem chung imbalance vs loi suat tuong lai ==")
    print(imbalance_vs_forward_return(bars))
