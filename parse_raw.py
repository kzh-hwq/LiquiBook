"""Doc du lieu tho (JSONL) tu collector.py -> bang pandas voi cac chi bao so lenh.

- Tim ban ghi stockInfo o bat ky cho nao trong thong diep (khong phu thuoc phong bi ben ngoai),
  vi chua biet chinh xac hinh dang thong diep that. Neu khac, chi can sua extract_records().
- Bo qua ban ghi khong hop le (ATO/ATC, thieu gia, so lenh bi cat nhau).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from metrics import book_metrics, to_num

VN_TZ = "Asia/Ho_Chi_Minh"
EXTRA_FIELDS = ["closePrice", "closeVol", "totalTradingVolume", "totalTradingValue",
                "foreignBuyValue", "foreignSellValue", "foreignNetValue", "foreignRoom"]


def extract_records(obj, depth: int = 0):
    """Sinh ra cac dict stockInfo (co 'symbol' va 'bidPrice1') long ben trong obj."""
    if depth > 4:
        return
    if isinstance(obj, dict):
        if "symbol" in obj and "bidPrice1" in obj:
            yield obj
            return
        for v in obj.values():
            yield from extract_records(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from extract_records(v, depth + 1)


def load_raw(folder: str | Path = "data", pattern: str = "raw_*.jsonl") -> pd.DataFrame:
    rows, bad_lines, skipped = [], 0, 0
    for path in sorted(Path(folder).glob(pattern)):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    ts = obj["ts"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    bad_lines += 1
                    continue
                for rec in extract_records(obj.get("raw")):
                    m = book_metrics(rec)
                    if m is None:
                        skipped += 1
                        continue
                    m["ts"] = ts
                    for k in EXTRA_FIELDS:
                        m[k] = to_num(rec.get(k))
                    rows.append(m)

    if not rows:
        df = pd.DataFrame(columns=["ts", "symbol", "mid", "spread", "spread_pct", "bid_depth",
                                   "ask_depth", "depth_value", "imbalance"] + EXTRA_FIELDS)
    else:
        df = pd.DataFrame(rows)
        df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(VN_TZ)
        df = df.sort_values(["symbol", "ts"]).reset_index(drop=True)
    df.attrs.update(bad_lines=bad_lines, skipped_invalid_book=skipped)
    return df


def filter_continuous(df: pd.DataFrame) -> pd.DataFrame:
    """Giu phien khop lenh lien tuc HOSE: 09:15-11:30 va 13:00-14:30 (gio Viet Nam).
    Loai ATO/ATC vi gia o cac phien do khong phan anh so lenh lien tuc."""
    if df.empty:
        return df
    t = df["ts"].dt.time
    from datetime import time as T
    mask = ((t >= T(9, 15)) & (t <= T(11, 30))) | ((t >= T(13, 0)) & (t <= T(14, 30)))
    return df[mask].reset_index(drop=True)


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "data"
    df = load_raw(folder)
    print(f"Ban ghi hop le: {len(df)} | dong JSON loi: {df.attrs['bad_lines']} | "
          f"so lenh khong hop le bi bo: {df.attrs['skipped_invalid_book']}")
    if not df.empty:
        print("Ma:", sorted(df['symbol'].unique()))
        print("Tu", df['ts'].min(), "den", df['ts'].max())
        out = Path("processed"); out.mkdir(exist_ok=True)
        df.to_csv(out / "book_metrics.csv", index=False)
        print("Da ghi processed/book_metrics.csv")
