"""Sinh du lieu GIA theo cau truc stockInfo trong tai lieu NEO API, de kiem thu khi chua co du lieu that.
Ghi vao thu muc rieng (mac dinh data_sample/) de KHONG lan voi du lieu that trong data/."""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN = timezone(timedelta(hours=7))
TICK = 50


def generate(folder="data_sample", day="2026-11-02", symbols=("HPG", "VCB", "FPT"),
             step_seconds=5, windows=(("09:00", "09:30"), ("13:00", "13:20")), seed=1):
    rng = random.Random(seed)
    Path(folder).mkdir(exist_ok=True)
    lines = []
    price = {s: 30000 + 5000 * i for i, s in enumerate(symbols)}
    total_value = {s: 0 for s in symbols}
    for a, b in windows:
        t = datetime.fromisoformat(f"{day}T{a}:00").replace(tzinfo=VN)
        end = datetime.fromisoformat(f"{day}T{b}:00").replace(tzinfo=VN)
        while t < end:
            for s in symbols:
                price[s] = max(TICK * 10, price[s] + rng.choice([-TICK, 0, 0, TICK]))
                bid1 = price[s]
                ask1 = bid1 + TICK * rng.choice([1, 1, 1, 2])
                rec = {"symbol": s}
                for i in range(3):
                    rec[f"bidPrice{i+1}"] = bid1 - TICK * i
                    rec[f"bidVol{i+1}"] = rng.randint(1, 300) * 100
                    rec[f"askPrice{i+1}"] = ask1 + TICK * i
                    rec[f"askVol{i+1}"] = rng.randint(1, 300) * 100
                rec["bidPrice1"], rec["askPrice1"] = f"{bid1}.0", f"{ask1}.0"   # mo phong kieu chuoi
                total_value[s] += rng.randint(0, 5_000_000)
                rec.update(closePrice=bid1, closeVol=100, totalTradingValue=total_value[s],
                           foreignNetValue=rng.randint(-10**9, 10**9))
                if a == "09:00" and t.time() < datetime.strptime("09:15", "%H:%M").time():
                    rec["bidPrice1"] = "ATO"                                    # phien ATO -> bi loai
                raw = rec if rng.random() < 0.5 else {"channel": "stockInfo", "data": rec}
                lines.append(json.dumps({"ts": t.isoformat(timespec="milliseconds"), "raw": raw}))
            lines.append(json.dumps({"ts": t.isoformat(), "raw": {"indexCode": "VN30", "advances": 10}}))
            t += timedelta(seconds=step_seconds)
    lines.insert(3, "{khong phai json")                                         # dong hong
    path = Path(folder) / f"raw_{day}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print("Da tao", generate())
