"""Chi bao thanh khoan va ap luc so lenh tu 3 muc gia mua/ban (kenh stockInfo).

Luu y: so lenh chi co 3 muc, nen day la ap luc trong top-3, khong phai toan bo so lenh.
"""
from __future__ import annotations

from typing import Optional


def to_num(x) -> Optional[float]:
    """Chuyen '29750.0' / 29750 -> float; 'ATO', 'ATC', None, '' -> None."""
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def book_metrics(msg: dict) -> Optional[dict]:
    """Tinh chi bao tu mot ban ghi stockInfo. Tra ve None neu du lieu khong hop le."""
    bid_p = [to_num(msg.get(f"bidPrice{i}")) for i in (1, 2, 3)]
    ask_p = [to_num(msg.get(f"askPrice{i}")) for i in (1, 2, 3)]
    bid_v = [to_num(msg.get(f"bidVol{i}")) or 0.0 for i in (1, 2, 3)]
    ask_v = [to_num(msg.get(f"askVol{i}")) or 0.0 for i in (1, 2, 3)]

    b1, a1 = bid_p[0], ask_p[0]
    if b1 is None or a1 is None or b1 <= 0 or a1 <= 0 or b1 >= a1:
        return None  # thieu gia, phien ATO/ATC, hoac so lenh bi cat nhau

    mid = (a1 + b1) / 2
    spread = a1 - b1
    bid_depth, ask_depth = sum(bid_v), sum(ask_v)
    total = bid_depth + ask_depth
    bid_value = sum(p * v for p, v in zip(bid_p, bid_v) if p)
    ask_value = sum(p * v for p, v in zip(ask_p, ask_v) if p)

    return {
        "symbol": msg.get("symbol"),
        "mid": mid,
        "spread": spread,
        "spread_pct": spread / mid * 100,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "depth_value": bid_value + ask_value,       # VND, do do sau top-3 hai phia
        "imbalance": (bid_depth - ask_depth) / total if total else None,  # -1..+1
    }
