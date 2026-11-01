"""Thu thap du lieu thi truong NEO API qua WebSocket, luu nguyen van (JSONL).
 
- Chi dung endpoint stock-stream (du lieu thi truong). KHONG ket noi trading-stream.
- Moi dong: {"ts": "<gio UTC+7>", "raw": <thong diep goc>}  -> phan tich sau, khong phu thuoc ten truong.
- Tu dong ket noi lai va dang nhap lai (token song 3 gio) khi mat ket noi.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
 
import certifi
import websocket
from dotenv import load_dotenv
 
from neo_auth import NeoAuth
 
load_dotenv(Path(__file__).resolve().parent / ".env")
 
VN_TZ = timezone(timedelta(hours=7))
WS_URL = os.getenv("NEO_WS_URL", "wss://neoapi.vpbanks.com.vn/stock-stream/broker")
SYMBOLS = [s.strip() for s in os.getenv("NEO_SYMBOLS", "VCB,HPG,FPT").split(",") if s.strip()]
 
def _env_list(name, default):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]
 
 
# Moi kenh co danh sach listId rieng (theo tai lieu 6.2)
SUBSCRIPTIONS = {
    "stockInfo": SYMBOLS,                                       # ma co phieu
    "marketInfo": _env_list("NEO_INDEXES", "VNINDEX,VN30"),      # chi so (do rong thi truong)
    "marketSession": _env_list("NEO_MARKETS", "HOSE"),           # phien giao dich
}
DATA_DIR = Path("data")
RECONNECT_EVERY = 2.5 * 3600   # ket noi lai truoc khi token het han (3h)
 
auth = NeoAuth()
_seen = {"n": 0}
 
 
def now_vn() -> datetime:
    return datetime.now(VN_TZ)
 
 
def write_line(obj: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"raw_{now_vn():%Y-%m-%d}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
 
 
def on_open(ws):
    print(f"[{now_vn():%H:%M:%S}] Da ket noi, dang xac thuc...")
    def _warn():
        if _seen["n"] == 0:
            print("(!) 15 giay roi chua nhan thong diep nao tu may chu.")
    threading.Timer(15, _warn).start()
    ws.send(json.dumps({"action": "auth", "data": auth.token()}))
 
 
def on_message(ws, message):
    _seen["n"] += 1
    if _seen["n"] <= 8:
        print(f"[msg {_seen['n']}] {str(message)[:300]}")
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        data = {"_non_json": message}
 
    if isinstance(data, dict) and data.get("type") == "auth":
        if str(data.get("status")).lower() in ("success", "ok", "1", "true"):
            print("Xac thuc WebSocket OK. Dang ky kenh...")
            for ch, ids in SUBSCRIPTIONS.items():
                ws.send(json.dumps({"type": "sub", "channel": ch, "listId": ids}))
        else:
            print("Xac thuc that bai:", data.get("data"))
            ws.close()
        return
 
    write_line({"ts": now_vn().isoformat(timespec="milliseconds"), "raw": data})
 
 
def on_error(ws, error):
    print("Loi:", error)
 
 
def on_close(ws, code, msg):
    print(f"[{now_vn():%H:%M:%S}] Dong ket noi ({code}).")
 
 
def run_once():
    ws = websocket.WebSocketApp(
        WS_URL, on_open=on_open, on_message=on_message,
        on_error=on_error, on_close=on_close,
    )
    # Dong chu dong sau RECONNECT_EVERY de lay token moi
    timer = threading.Timer(RECONNECT_EVERY, ws.close)
    timer.daemon = True
    timer.start()
    # certifi: tranh loi CERTIFICATE_VERIFY_FAILED tren Python cai tu python.org (Mac)
    ws.run_forever(ping_interval=20, ping_timeout=10,
                   sslopt={"ca_certs": certifi.where()})
    timer.cancel()
 
 
if __name__ == "__main__":
    delay = 2
    while True:
        started = time.time()
        try:
            run_once()
        except Exception as e:  # noqa: BLE001
            print("Loi khong mong doi:", e)
        # Neu ket noi song lau thi dat lai do tre; neu chet nhanh thi tang dan (toi da 60s)
        delay = 2 if time.time() - started > 60 else min(delay * 2, 60)
        print(f"Ket noi lai sau {delay}s...")
        time.sleep(delay)
 