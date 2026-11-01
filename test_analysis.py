import math

import numpy as np
import pandas as pd

import analysis
import make_sample
import parse_raw


def _bars(tmp_path):
    p = make_sample.generate(folder=str(tmp_path))
    df = parse_raw.filter_continuous(parse_raw.load_raw(tmp_path))
    return df, analysis.add_signals(analysis.to_bars(df))


def test_extract_records_handles_wrappers():
    rec = {"symbol": "HPG", "bidPrice1": 1}
    assert list(parse_raw.extract_records(rec)) == [rec]
    assert list(parse_raw.extract_records({"channel": "stockInfo", "data": rec})) == [rec]
    assert list(parse_raw.extract_records({"data": [rec, rec]})) == [rec, rec]
    assert list(parse_raw.extract_records({"indexCode": "VN30"})) == []


def test_load_raw_counts_and_filters(tmp_path):
    make_sample.generate(folder=str(tmp_path))
    raw = parse_raw.load_raw(tmp_path)
    assert raw.attrs["bad_lines"] == 1                 # 1 dong JSON hong
    assert raw.attrs["skipped_invalid_book"] > 0       # ban ghi ATO bi bo
    assert set(raw["symbol"]) == {"HPG", "VCB", "FPT"}
    assert str(raw["ts"].dt.tz) == "Asia/Ho_Chi_Minh"
    cont = parse_raw.filter_continuous(raw)
    t = cont["ts"].dt.time
    assert (t >= pd.Timestamp("09:15").time()).all()   # khong con ATO


def test_rolling_z_excludes_current_point_and_flat_series():
    s = pd.Series([1.0] * 20 + [10.0])
    z = analysis.rolling_z(s, window=10, min_periods=5)
    assert z.iloc[:20].isna().all()                    # chuoi phang: std = 0 -> NaN
    s2 = pd.Series(list(np.tile([1.0, 2.0], 10)) + [10.0])
    z2 = analysis.rolling_z(s2, window=10, min_periods=5)
    assert z2.iloc[-1] > 5                             # cu soc lon -> z cao


def test_bars_and_signals(tmp_path):
    _, bars = _bars(tmp_path)
    assert {"z_spread", "z_imbalance", "alert_wide_spread"} <= set(bars.columns)
    assert bars["spread_pct"].min() > 0
    assert bars["imbalance"].between(-1, 1).all()


def test_liquidity_ranking_orders_by_construction():
    ts = pd.date_range("2026-11-02 09:20", periods=10, freq="1min", tz="Asia/Ho_Chi_Minh")
    rows = []
    for sym, spread, depth, val in [("GOOD", 0.05, 9e9, 9e10), ("BAD", 0.50, 1e8, 1e9), ("MID", 0.20, 1e9, 1e10)]:
        for t in ts:
            rows.append(dict(ts=t, symbol=sym, spread_pct=spread, depth_value=depth,
                             totalTradingValue=val, mid=1.0, imbalance=0.0))
    r = analysis.liquidity_ranking(pd.DataFrame(rows))
    assert list(r["symbol"]) == ["GOOD", "MID", "BAD"]
    assert math.isclose(r.loc[0, "liquidity_score"], 100.0)
    assert math.isclose(r.loc[2, "liquidity_score"], 0.0)


def test_validation_runs_and_is_bounded(tmp_path):
    _, bars = _bars(tmp_path)
    res = analysis.imbalance_vs_forward_return(bars, horizon=3)
    assert res["n"] > 10
    assert -1 <= res["spearman"] <= 1
    assert res["hit_rate"] is None or 0 <= res["hit_rate"] <= 1


def test_foreign_flow(tmp_path):
    _, bars = _bars(tmp_path)
    ff = analysis.foreign_flow(bars)
    assert {"symbol", "date", "foreign_net_value"} <= set(ff.columns)
    assert len(ff) == 3
